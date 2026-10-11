import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

import config
from etl.wczytanie_i_czyszczenie_cech.pozostale import dodaj_pozostale
from etl.sasiedztwo_cenowe.polska import dodaj_sasiedztwo, CECHY

KOLUMNY = [
    "klucz_transakcji",
    "dok_data",
    "cena_m2",
    "dzi_id_dzialki",
    "dzi_sposob_uzyt",
    "teryt_woj",
    "teryt_gmina",
    "teryt_obreb",
    "x_2180",
    "y_2180",
    "powierzchnia_m2",
    "pole_geom_m2",
    "obwod_m",
    "dzi_adres",
    "dzi_przezn_wmpzp",
]


def przygotuj_pozostale():
    wejscie = Path(config.SCIEZKA_CECHY_OSM) / "transakcje.parquet"
    cel = Path(config.SCIEZKA_PELNE_CECHY)
    if cel.exists():
        raise FileExistsError(f"Wynik juz istnieje: {cel}")
    if shutil.disk_usage(cel.parent).free < (config.ZAPAS_DYSKU_GIB + 1) * 1024**3:
        raise RuntimeError("Potrzeba 10 GiB zapasu i miejsca na wynik")

    poczatek = time.monotonic()
    postep = Path(config.SCIEZKA_POSREDNIE) / "cechy_postep.json"
    stan = {
        "status": "cechy_podstawowe",
        "wejscie": str(wejscie),
        "test_od": config.TEST_OD,
    }
    postep.write_text(json.dumps(stan, indent=2))

    try:
        dane = pq.read_table(wejscie, columns=KOLUMNY).to_pandas()
        if not dane.klucz_transakcji.is_unique:
            raise ValueError("Powtorzone klucze transakcji")
        print(
            f"Pozostale cechy: {len(dane):,} transakcji, {dane.teryt_woj.nunique()} wojewodztw",
            flush=True,
        )
        dane = dodaj_pozostale(dane)
        if (
            not np.isfinite(dane.log_powierzchnia).all()
            or not dane.wskaznik_zwartosci.between(0, 1 + 1e-9).all()
        ):
            raise ValueError("Niepoprawne cechy geometryczne")

        stan["status"] = "sasiedztwo_grupowe"
        postep.write_text(json.dumps(stan, indent=2))

        def pokaz_postep(wykonane, wszystkie, eta):
            stan.update(
                status="sasiedztwo_przestrzenne",
                wykonane=wykonane,
                wszystkie=wszystkie,
                eta_sekundy=eta,
            )
            stan["aktualizacja_utc"] = datetime.now(timezone.utc).isoformat()
            postep.write_text(json.dumps(stan, indent=2))

        dane = dodaj_sasiedztwo(dane, config.TEST_OD, pokaz_postep)
        nowe = [nazwa for nazwa in dane.columns if nazwa not in KOLUMNY]
        cechy = dane.set_index("klucz_transakcji")[nowe]

        osm = json.loads((wejscie.parent / "podsumowanie.json").read_text())["cechy"]
        podstawowe = [
            "tran_sprzedajacy",
            "nier_prawo",
            "dzi_sposob_uzyt",
            "teryt_woj",
            "teryt_powiat",
            "teryt_gmina",
            "rok",
            "x_2180",
            "y_2180",
            "powierzchnia_m2",
        ]
        wejscia_modelu = podstawowe + osm + [n for n in nowe if n != "zbior"]
        kategorie = [
            "tran_sprzedajacy",
            "nier_prawo",
            "dzi_sposob_uzyt",
            "teryt_woj",
            "teryt_powiat",
            "teryt_gmina",
            "miejscowosc",
        ]
        manifest = {
            "target": "cena_m2",
            "cechy": wejscia_modelu,
            "kategoryczne": kategorie,
            "liczbowe": [n for n in wejscia_modelu if n not in kategorie],
            "test_od": config.TEST_OD,
            "zasady": "Ceny referencyjne tylko z treningu, scisle wczesniejszy dzien, bez sprzedazy tej samej dzialki. Zmiana daty podzialu wymaga ponownego obliczenia sasiedztwa. Kodowanie kategorii i imputacja dopiero na treningu.",
        }
        parquet = pq.ParquetFile(wejscie)
        pola = list(parquet.schema_arrow)
        for nazwa in nowe:
            typ = pa.string() if nazwa in {"miejscowosc", "zbior"} else pa.float64()
            pola.append(pa.field(nazwa, typ))
        schemat = pa.schema(pola, metadata=parquet.schema_arrow.metadata)
        stan["status"] = "zapis"
        postep.write_text(json.dumps(stan, indent=2))

        with TemporaryDirectory(prefix=".pelne-cechy-", dir=cel.parent) as katalog:
            roboczy = Path(katalog)
            with pq.ParquetWriter(
                roboczy / "transakcje.parquet", schemat, compression="zstd"
            ) as zapis:
                for partia in parquet.iter_batches(batch_size=25000):
                    if (
                        shutil.disk_usage(roboczy).free
                        < (config.ZAPAS_DYSKU_GIB + 1) * 1024**3
                    ):
                        raise RuntimeError("Malo miejsca podczas zapisu")
                    ramka = partia.to_pandas()
                    wybrane = cechy.loc[ramka.klucz_transakcji]
                    for nazwa in nowe:
                        ramka[nazwa] = wybrane[nazwa].to_numpy()
                    zapis.write_table(
                        pa.Table.from_pandas(
                            ramka, schema=schemat, preserve_index=False
                        )
                    )

            raport = {
                "wiersze": len(dane),
                "kolumny": len(schemat),
                "liczba_cech": len(wejscia_modelu),
                "dodane_kolumny": nowe,
                "test_od": config.TEST_OD,
                "podzial": dane.zbior.value_counts().to_dict(),
                "wojewodztwa": dane.groupby(["teryt_woj", "zbior"])
                .size()
                .unstack(fill_value=0)
                .to_dict(),
                "braki_nowych_cech": cechy.isna().sum().to_dict(),
                "stale_nowe_cechy": [n for n in nowe if cechy[n].nunique() <= 1],
                "czas_sekundy": round(time.monotonic() - poczatek, 2),
                "wejscie": str(wejscie.resolve()),
                "bajty_wejscia": wejscie.stat().st_size,
                "bajty_wyniku": (roboczy / "transakcje.parquet").stat().st_size,
            }
            (roboczy / "cechy_modelu.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2)
            )
            (roboczy / "podsumowanie.json").write_text(
                json.dumps(raport, ensure_ascii=False, indent=2)
            )
            roboczy.rename(cel)
        stan.update(
            status="zakonczone",
            wyjscie=str(cel),
            wiersze=len(dane),
            cechy=len(wejscia_modelu),
        )
        print(json.dumps(raport, ensure_ascii=False, indent=2), flush=True)

    except BaseException as blad:
        stan.update(status="przerwane", blad=str(blad))
        raise

    finally:
        stan["aktualizacja_utc"] = datetime.now(timezone.utc).isoformat()
        postep.write_text(json.dumps(stan, indent=2))


if __name__ == "__main__":
    przygotuj_pozostale()
