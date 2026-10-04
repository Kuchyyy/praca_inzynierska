import gc
import json
import shutil
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from scipy.spatial import cKDTree

import config
from etl.cechy_osm.warstwy import przygotuj_warstwy, WARSTWY


ODLEGLOSCI = {
    "budynki": "odl_najblizszy_budynek_m", "mieszkalne": "odl_budynek_mieszkalny_m",
    "drogi": "odl_droga_dowolna_m", "utwardzone": "odl_droga_utwardzona_m",
    "glowne": "odl_droga_glowna_m", "lokalne": "odl_droga_lokalna_m",
    "autostrady": "odl_autostrada_m", "wezly": "odl_wezel_autostrady_m",
    "przystanki": "odl_przystanek_m", "miejscowosci": "odl_najblizsza_miejscowosc_m",
    "miasta_10k": "odl_miasto_pow_10k_m", "miasta_50k": "odl_miasto_pow_50k_m",
    "wroclaw": "odl_wroclaw_m", "szkoly": "odl_szkola_m", "sklepy": "odl_sklep_spozywczy_m",
    "przedszkola": "odl_przedszkole_m", "woda": "odl_woda_m", "granica": "odl_granica_panstwa_m",
}


def odleglosci_do_geometrii(punkty, geometrie):
    wynik = np.full(len(punkty), np.nan)
    if len(geometrie) == 0:
        return wynik
    drzewo = shapely.STRtree(geometrie)
    for start in range(0, len(punkty), 10000):
        czesc = punkty[start:start + 10000]
        indeksy, dystanse = drzewo.query_nearest(czesc, all_matches=False, return_distance=True)
        wynik[start + indeksy[0]] = dystanse
    return wynik


def pokrycie(punkty, geometrie, promien=500):
    wynik = np.full(len(punkty), np.nan)
    if len(geometrie) == 0:
        return wynik
    drzewo = shapely.STRtree(geometrie)
    for start in range(0, len(punkty), 1000):
        kola = shapely.buffer(punkty[start:start + 1000], promien, quad_segs=16)
        sasiedzi = drzewo.query(kola, predicate="intersects")
        for i, kolo in enumerate(kola):
            indeksy = sasiedzi[1, sasiedzi[0] == i]
            if len(indeksy) == 0:
                wynik[start + i] = 0
                continue
            fragmenty = shapely.intersection(geometrie[indeksy], kolo)
            # Nakladajace sie poligony liczymy tylko raz.
            wynik[start + i] = shapely.union_all(fragmenty).area / kolo.area
    return np.clip(wynik, 0, 1)


def policz_osm():
    warstwy = przygotuj_warstwy()
    wejscie = Path(config.SCIEZKA_PO_EGIB) / "transakcje.parquet"
    cel = Path(config.SCIEZKA_CECHY_OSM)
    if cel.exists():
        raise FileExistsError(f"Wynik OSM juz istnieje: {cel}")

    dane = pq.read_table(wejscie, columns=["klucz_transakcji", "x_2180", "y_2180", "do_modelu"]).to_pandas()
    dane = dane[dane.do_modelu].reset_index(drop=True)
    xy = dane[["x_2180", "y_2180"]].to_numpy()
    if not np.isfinite(xy).all():
        raise ValueError("Rekord do modelu nie ma poprawnego srodka")
    punkty = shapely.points(xy)
    cechy = pd.DataFrame(index=dane.klucz_transakcji)
    postep = Path(config.SCIEZKA_POSREDNIE) / "osm_postep.json"
    poczatek = time.monotonic()
    odleglosc_rzeka = np.full(len(dane), np.nan)
    pustki = []

    for numer, warstwa in enumerate(WARSTWY, 1):
        if shutil.disk_usage(cel.parent).free < (config.ZAPAS_DYSKU_GIB + 1) * 1024**3:
            raise RuntimeError("Malo miejsca na cechy OSM")
        print(f"OSM {numer}/{len(WARSTWY)}: {warstwa}", flush=True)
        stan = {"status": "cechy_osm", "warstwa": warstwa, "wykonane": numer-1, "wszystkie": len(WARSTWY), "czas_sekundy": round(time.monotonic()-poczatek)}
        postep.write_text(json.dumps(stan, indent=2))
        tabela = pq.read_table(warstwy / (warstwa + ".parquet")).to_pandas()
        geometrie = shapely.from_wkb(tabela.geometry.to_numpy())
        if tabela.empty:
            pustki.append(warstwa)

        if warstwa in ODLEGLOSCI:
            cechy[ODLEGLOSCI[warstwa]] = odleglosci_do_geometrii(punkty, geometrie)

        if warstwa in {"budynki", "poi", "miasta"}:
            promienie = [250, 500, 1000] if warstwa == "budynki" else [1000]
            if not tabela.empty:
                drzewo = cKDTree(tabela[["x", "y"]].to_numpy())
            if warstwa == "miasta":
                cechy["ludnosc_najblizszego_miasta"] = np.nan
                if not tabela.empty:
                    _, indeksy = drzewo.query(xy)
                    cechy["ludnosc_najblizszego_miasta"] = tabela.population.to_numpy()[indeksy]
            else:
                for promien in promienie:
                    nazwa = f"liczba_budynkow_{promien}m" if warstwa == "budynki" else "liczba_poi_1km"
                    cechy[nazwa] = np.nan
                    if not tabela.empty:
                        cechy[nazwa] = drzewo.query_ball_point(xy, r=promien, return_length=True)
            if not tabela.empty:
                del drzewo

        if warstwa in {"las", "zabudowa"}:
            nazwa = "udzial_lasu_500m" if warstwa == "las" else "udzial_zabudowy_500m"
            cechy[nazwa] = pokrycie(punkty, geometrie)
            if warstwa == "zabudowa":
                odleglosci = odleglosci_do_geometrii(punkty, geometrie)
                cechy["czy_w_terenie_zabudowanym"] = np.where(np.isfinite(odleglosci), (odleglosci == 0).astype(float), np.nan)

        if warstwa == "rzeki":
            odleglosc_rzeka = odleglosci_do_geometrii(punkty, geometrie)

        del tabela, geometrie
        gc.collect()

    # Brak calej warstwy nie oznacza, ze nie ma wody.
    woda = cechy["odl_woda_m"].to_numpy()
    blisko = (woda <= 200) | (odleglosc_rzeka <= 200)
    znane = (np.isfinite(woda) & np.isfinite(odleglosc_rzeka)) | blisko
    cechy["czy_woda_w_200m"] = np.where(znane, blisko.astype(float), np.nan)
    cechy = cechy.astype(float)

    parquet = pq.ParquetFile(wejscie)
    pola = list(parquet.schema_arrow) + [pa.field(nazwa, pa.float64()) for nazwa in cechy.columns]
    schemat = pa.schema(pola, metadata=parquet.schema_arrow.metadata)
    with TemporaryDirectory(prefix=".cechy-osm-", dir=cel.parent) as katalog:
        roboczy = Path(katalog)
        with pq.ParquetWriter(roboczy / "transakcje.parquet", schemat, compression="zstd") as zapis:
            for partia in parquet.iter_batches(batch_size=25000):
                if shutil.disk_usage(roboczy).free < (config.ZAPAS_DYSKU_GIB + 1) * 1024**3:
                    raise RuntimeError("Malo miejsca podczas zapisu cech")
                ramka = partia.to_pandas()
                ramka = ramka[ramka.do_modelu].copy()
                if ramka.empty:
                    continue
                for nazwa in cechy.columns:
                    ramka[nazwa] = cechy.loc[ramka.klucz_transakcji, nazwa].to_numpy()
                zapis.write_table(pa.Table.from_pandas(ramka, schema=schemat, preserve_index=False))

        opis = {"wiersze": len(dane), "cechy": list(cechy.columns), "braki": cechy.isna().sum().to_dict(), "puste_warstwy": pustki, "osm": json.loads((warstwy / "opis.json").read_text()), "czas_sekundy": round(time.monotonic()-poczatek), "uwagi": "Aktualne OSM przy historycznych transakcjach. Odleglosci euklidesowe od srodka dzialki, bez gwarancji dostepu prawnego. Licznosci budynkow i POI po centroidach; POI to obiekty OSM, mozliwe powtorne reprezentacje. Bez ograniczania do wojewodztwa; zasieg ograniczony ekstraktem Polski."}
        (roboczy / "podsumowanie.json").write_text(json.dumps(opis, indent=2, ensure_ascii=False))
        roboczy.rename(cel)
    postep.write_text(json.dumps({"status": "zakonczone", "wiersze": len(dane), "wyjscie": str(cel)}, indent=2))
    print(f"Gotowe: {cel}, {len(dane):,} transakcji, {len(cechy.columns)} cech OSM", flush=True)


if __name__ == "__main__":
    policz_osm()
