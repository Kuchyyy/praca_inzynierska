from datetime import date
from pathlib import Path

import config
from etl.uldk.uzupelnij import pobierz_brakujace_granice, przelicz_po_uldk
from etl.wczytanie_i_czyszczenie_cech.wczytywanie import oczysc_plik

if __name__ == "__main__":
    wejscie = Path(config.SCIEZKA_SUROWE)
    oczyszczone = Path(config.SCIEZKA_OCZYSZCZONE)
    po_uldk = Path(config.SCIEZKA_PO_ULDK)
    data_do = date.fromisoformat(config.DATA_DO)

    print("1. Czyszczenie transakcji RCN")

    if oczyszczone.exists():
        print(f"Korzystam z zapisanego wyniku: {oczyszczone}")
    else:
        oczysc_plik(
            wejscie=wejscie,
            wyjscie=oczyszczone,
            data_do=data_do,
            wielkosc_partii=config.WIELKOSC_PARTII,
            wojewodztwo=config.WOJEWODZTWO,
            limit_uldk=config.LIMIT_ULDK,
        )

    print()
    print("2. Pobieranie brakujacych granic ULDK")

    # Teraz pobieranie juz dziala osobno. Nie startujemy drugiej kopii.
    if not config.UZUPELNIJ_ULDK:
        print("Etap wylaczony w config.py. Podglad pobierania: python postep.py")
    elif po_uldk.exists():
        print(f"Wynik po ULDK juz istnieje: {po_uldk}")
    else:
        opis = pobierz_brakujace_granice()

        print()
        print("3. Przeliczenie powierzchni i cen po ULDK")

        przelicz_po_uldk(opis)

    print()
    print("Koniec przygotowania danych. OSM i modele to kolejne etapy.")
