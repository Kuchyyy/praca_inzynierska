import os

import config
from etl.wczytywanie import wczytaj_dane
from etl.czyszczenie import wyczysc, dokoncz_czyszczenie
from etl.geometria import dodaj_geometrie
from etl.cechy_podstawowe import dodaj_cechy_podstawowe
from etl.cechy_geometryczne import dodaj_cechy_geometryczne
from etl.raport import pokaz_podsumowanie


def przygotuj_katalogi():
    for katalog in [config.SCIEZKA_POSREDNIE, config.SCIEZKA_ODRZUCONE, config.SCIEZKA_GOTOWE]:
        os.makedirs(katalog, exist_ok=True)


def uruchom():
    przygotuj_katalogi()

    df = wczytaj_dane()

    df = wyczysc(df)
    df = dodaj_geometrie(df)
    # Geometria najpierw, bo dalsze filtry potrzebuja powierzchni w m2.
    df = dokoncz_czyszczenie(df)

    df = dodaj_cechy_podstawowe(df)
    df = dodaj_cechy_geometryczne(df)

    sciezka = os.path.join(config.SCIEZKA_GOTOWE, "dane_z_cechami.parquet")
    df.drop(columns=["geometry"]).to_parquet(sciezka, index=False)

    pokaz_podsumowanie(df)

    print(f"Gotowy zbior zapisany do {sciezka}")
    print()


if __name__ == "__main__":
    uruchom()
