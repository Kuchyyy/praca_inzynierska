from datetime import date
from pathlib import Path

import config
from etl.audyt_danych import audytuj_dane
from etl.walidacja_modelu import przygotuj_dane_walidacyjne
from etl.pozostale_cechy import przygotuj_pozostale
from etl.cechy_osm.polska import policz_osm
from etl.egib.paczki import uzupelnij_egib
from etl.uldk.uzupelnij import pobierz_brakujace_granice, przelicz_po_uldk
from etl.wczytanie_i_czyszczenie_cech.wczytywanie import oczysc_plik
from model.trenuj import trenuj_modele

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
    print("2. Uzupelnienie granic i przeliczenie powierzchni")

    # Teraz pobieranie juz dziala osobno. Nie startujemy drugiej kopii.
    if config.UZUPELNIJ_EGIB:
        uzupelnij_egib()
    elif not config.UZUPELNIJ_ULDK:
        print("Etap wylaczony w config.py. Podglad pobierania: python postep.py")
    elif po_uldk.exists():
        print(f"Wynik po ULDK juz istnieje: {po_uldk}")
    else:
        opis = pobierz_brakujace_granice()

        print()
        print("3. Przeliczenie powierzchni i cen po ULDK")

        przelicz_po_uldk(opis)

    print()
    if config.LICZ_OSM:
        print("4. Cechy otoczenia z OSM")
        policz_osm()

    if config.LICZ_POZOSTALE_CECHY:
        print("5. Pozostale cechy i sasiedztwo cenowe Polski")
        przygotuj_pozostale()

    if config.AUDYTUJ_DANE:
        print("6. Audyt danych i kontrakt wejsc modelu")
        audytuj_dane()
        print("7. Osobne sasiedztwo cenowe dla walidacji czasowej")
        przygotuj_dane_walidacyjne()

    if config.TRENUJ_MODELE:
        print("8. Trening modeli do wyceny")
        trenuj_modele()

    print("Koniec wybranych etapow przygotowania danych.")
    print("Serwer wyceny dla panelu: python api.py")
