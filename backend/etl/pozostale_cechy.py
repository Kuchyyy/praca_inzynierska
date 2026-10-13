from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

import config
from etl.sasiedztwo_cenowe.polska import dodaj_sasiedztwo
from etl.wczytanie_i_czyszczenie_cech.pozostale import dodaj_pozostale

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
    "dzi_przezn_wmpzp",
]


def przygotuj_pozostale():
    wejscie = config.SCIEZKA_CECHY_OSM
    cel = Path(config.SCIEZKA_PELNE_CECHY)

    dane = pq.read_table(wejscie, columns=KOLUMNY).to_pandas()
    print(f"Pozostałe cechy: {len(dane):,} transakcji", flush=True)
    dane = dodaj_pozostale(dane)
    dane = dodaj_sasiedztwo(dane, config.TEST_OD)

    nowe = [nazwa for nazwa in dane.columns if nazwa not in KOLUMNY]
    cechy = dane.set_index("klucz_transakcji")[nowe]

    parquet = pq.ParquetFile(wejscie)
    pola = list(parquet.schema_arrow)
    for nazwa in nowe:
        typ = pa.string() if nazwa == "zbior" else pa.float64()
        pola.append(pa.field(nazwa, typ))
    schemat = pa.schema(pola)

    cel.parent.mkdir(parents=True, exist_ok=True)
    roboczy = cel.with_suffix(".czesc")
    with pq.ParquetWriter(roboczy, schemat, compression="zstd") as zapis:
        for partia in parquet.iter_batches(batch_size=config.WIELKOSC_PARTII):
            ramka = partia.to_pandas()
            wybrane = cechy.loc[ramka["klucz_transakcji"]]
            for nazwa in nowe:
                ramka[nazwa] = wybrane[nazwa].to_numpy()
            zapis.write_table(pa.Table.from_pandas(ramka, schema=schemat, preserve_index=False))

    roboczy.rename(cel)
    print(f"Gotowe: {cel}, trening: {(dane['zbior'] == 'trening').sum():,}, test: {(dane['zbior'] == 'test').sum():,}")
