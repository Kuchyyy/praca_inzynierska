import runpy
from pathlib import Path

import config
from etl.etap1_pobranie.pobierz_dane import pobierz_dane
from db.import_postgis import importuj_dane
from etl.etap2_4_czyszczenie.czyszczenie import oczysc
from etl.etap3_granice.uldk import uzupelnij_uldk
from etl.etap3_granice.egib import uzupelnij_egib
from etl.etap5_osm.cechy_osm import policz_osm
from etl.etap6_cechy.polacz_cechy import polacz_cechy


print("1. Pobranie RCN i mapy OSM")
pobierz_dane()

print("\n2. Czyszczenie transakcji RCN")
if Path(config.SCIEZKA_OCZYSZCZONE).exists():
    print(f"Gotowe wcześniej: {config.SCIEZKA_OCZYSZCZONE}")
else:
    oczysc(config.SCIEZKA_SUROWE, config.SCIEZKA_OCZYSZCZONE)

print("\n3. Brakujące granice działek z ULDK i paczek EGiB")
if config.UZUPELNIJ_ULDK:
    uzupelnij_uldk()
if config.UZUPELNIJ_EGIB:
    uzupelnij_egib()

print("\n4. Ponowne czyszczenie z uzupełnionymi granicami")
if Path(config.SCIEZKA_Z_GRANICAMI).exists():
    print(f"Gotowe wcześniej: {config.SCIEZKA_Z_GRANICAMI}")
else:
    oczysc(config.SCIEZKA_SUROWE, config.SCIEZKA_Z_GRANICAMI)

print("\n5. Cechy otoczenia z OSM")
if Path(config.SCIEZKA_CECHY_OSM).exists():
    print(f"Gotowe wcześniej: {config.SCIEZKA_CECHY_OSM}")
else:
    policz_osm()

print("\n6. Cechy działki i sąsiedztwo cenowe")
if Path(config.SCIEZKA_PELNE_CECHY).exists():
    print(f"Gotowe wcześniej: {config.SCIEZKA_PELNE_CECHY}")
else:
    polacz_cechy()

print("\n7. Import do bazy PostGIS")
if config.IMPORTUJ_DO_BAZY:
    importuj_dane()

print("\n8. Trening modeli i eksperymenty z cechami")
if config.TRENUJ_MODELE:
    runpy.run_path("modele.py")
if config.WAZNOSC_CECH:
    runpy.run_path("waznosc_cech.py")
if config.SYMULACJA_CECH:
    runpy.run_path("eksperymenty_cech.py")
if config.WALIDACJA_KROCZACA:
    runpy.run_path("walidacja_kroczaca_modele.py")

print("\nKoniec. Serwer wyceny dla panelu")
