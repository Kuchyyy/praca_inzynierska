import gc
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from scipy.spatial import cKDTree

import config
from etl.cechy_osm.warstwy import przygotuj_warstwy, WARSTWY


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
            wynik[start + i] = shapely.union_all(fragmenty).area / kolo.area
    return np.clip(wynik, 0, 1)


def policz_osm():
    warstwy = przygotuj_warstwy()
    wejscie = config.SCIEZKA_Z_GRANICAMI
    cel = Path(config.SCIEZKA_CECHY_OSM)

    dane = pq.read_table(wejscie, columns=["klucz_transakcji", "x_2180", "y_2180", "do_modelu"]).to_pandas()
    dane = dane[dane["do_modelu"]].reset_index(drop=True)
    xy = dane[["x_2180", "y_2180"]].to_numpy()
    punkty = shapely.points(xy)
    cechy = pd.DataFrame(index=dane["klucz_transakcji"])

    for numer, warstwa in enumerate(WARSTWY, 1):
        print(f"OSM {numer}/{len(WARSTWY)}: {warstwa}", flush=True)
        tabela = pq.read_table(warstwy / (warstwa + ".parquet")).to_pandas()
        geometrie = shapely.from_wkb(tabela["geometry"].to_numpy())

        if warstwa == "budynki":
            cechy["odl_najblizszy_budynek_m"] = odleglosci_do_geometrii(punkty, geometrie)
            drzewo = cKDTree(tabela[["x", "y"]].to_numpy())
            cechy["liczba_budynkow_1000m"] = drzewo.query_ball_point(xy, r=1000, return_length=True)

        if warstwa == "drogi":
            cechy["odl_droga_dowolna_m"] = odleglosci_do_geometrii(punkty, geometrie)

        if warstwa == "utwardzone":
            cechy["odl_droga_utwardzona_m"] = odleglosci_do_geometrii(punkty, geometrie)

        if warstwa == "las":
            cechy["udzial_lasu_500m"] = pokrycie(punkty, geometrie)

        if warstwa == "miasta_50k":
            cechy["odl_miasto_pow_50k_m"] = odleglosci_do_geometrii(punkty, geometrie)

        if warstwa == "poi":
            drzewo = cKDTree(tabela[["x", "y"]].to_numpy())
            cechy["liczba_poi_1km"] = drzewo.query_ball_point(xy, r=1000, return_length=True)

        del tabela, geometrie
        gc.collect()

    cechy = cechy.astype(float)

    parquet = pq.ParquetFile(wejscie)
    pola = list(parquet.schema_arrow) + [pa.field(nazwa, pa.float64()) for nazwa in cechy.columns]
    schemat = pa.schema(pola)
    cel.parent.mkdir(parents=True, exist_ok=True)
    roboczy = cel.with_suffix(".czesc")

    with pq.ParquetWriter(roboczy, schemat, compression="zstd") as zapis:
        for partia in parquet.iter_batches(batch_size=config.WIELKOSC_PARTII):
            ramka = partia.to_pandas()
            ramka = ramka[ramka["do_modelu"]].copy()
            if ramka.empty:
                continue
            for nazwa in cechy.columns:
                ramka[nazwa] = cechy.loc[ramka["klucz_transakcji"], nazwa].to_numpy()
            zapis.write_table(pa.Table.from_pandas(ramka, schema=schemat, preserve_index=False))

    roboczy.rename(cel)
    print(f"Gotowe: {cel}, {len(dane):,} transakcji, {len(cechy.columns)} cech OSM", flush=True)
