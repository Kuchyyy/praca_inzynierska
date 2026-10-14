from pathlib import Path

import pandas as pd

import config
from etl.etap6_cechy.sasiedztwo import dodaj_sasiedztwo
from etl.etap6_cechy.cechy_dzialki import dodaj_pozostale


def polacz_cechy():
    print("Wczytanie działek z cechami OSM")
    dane = pd.read_parquet(config.SCIEZKA_CECHY_OSM)
    kolumny_przed = list(dane.columns)
    print(f"  działek: {len(dane):,}")

    print("Cechy działki: logarytm powierzchni, czas, kształt, przeznaczenie")
    dane = dodaj_pozostale(dane)

    print("Sąsiedztwo cenowe i podział na trening i test")
    dane = dodaj_sasiedztwo(dane, config.TEST_OD)

    for nazwa in dane.columns:
        if nazwa not in kolumny_przed and nazwa != "zbior":
            dane[nazwa] = dane[nazwa].astype(float)

    Path(config.SCIEZKA_PELNE_CECHY).parent.mkdir(parents=True, exist_ok=True)
    dane.to_parquet(config.SCIEZKA_PELNE_CECHY, index=False)

    trening = (dane["zbior"] == "trening").sum()
    test = (dane["zbior"] == "test").sum()
    print(f"Zapisano: {config.SCIEZKA_PELNE_CECHY}, trening: {trening:,}, test: {test:,}")
