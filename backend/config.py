# Sciezki i progi. Zmiany ustawien robie tutaj.

SCIEZKA_SUROWE = "db/dane/surowe/rcn/0_transakcje_ceny_dzialki.parquet"
SCIEZKA_OCZYSZCZONE = "db/dane/gotowe/polska_oczyszczone"
DATA_DO = "2026-10-02"
WIELKOSC_PARTII = 25000
ZAPAS_DYSKU_GIB = 10
SCIEZKA_POSREDNIE = "db/dane/posrednie"
SCIEZKA_ULDK_GRANICE = "db/dane/posrednie/uldk_granice.sqlite"
WOJEWODZTWO = None
LIMIT_ULDK = 0
PRZERWA_ULDK = 0.1
UZUPELNIJ_ULDK = False
SCIEZKA_PO_ULDK = "db/dane/gotowe/polska_po_uldk"

SCIEZKA_ODRZUCONE = "db/dane/posrednie/odrzucone"
SCIEZKA_GOTOWE = "db/dane/gotowe"


ROK_OD = 2015

POWIERZCHNIA_MIN = 100
POWIERZCHNIA_MAX = 200000


# Dopuszczalny stosunek powierzchni z pliku do pola z geometrii.
TOLERANCJA_POLA_DOL = 0.80
TOLERANCJA_POLA_GORA = 1.25


KOLUMNY_POTRZEBNE = [
    "teryt",
    "serwis_rcn",
    "tran_przestrzen_nazw",
    "tran_wersja_id",
    "tran_lokalny_id_iip",
    "tran_rodzaj_trans",
    "tran_sprzedajacy",
    "tran_kupujacy",
    "tran_rodzaj_rynku",
    "tran_vat",
    "tran_cena_brutto",
    "dok_data",
    "nier_rodzaj",
    "nier_prawo",
    "nier_udzial",
    "nier_pow_gruntu",
    "nier_cena_brutto",
    "nier_vat",
    "dzi_id_dzialki",
    "dzi_nr_dzialki",
    "dzi_cena_brutto",
    "dzi_vat",
    "dzi_przezn_wmpzp",
    "dzi_pow_ewid",
    "dzi_sposob_uzyt",
    "dzi_adres",
    "geometry",
]

UZUPELNIJ_EGIB = False
SCIEZKA_PO_EGIB = "db/dane/gotowe/polska_po_egib"

SCIEZKA_OSM = "db/dane/surowe/osm/poland-260930.osm.pbf"
SCIEZKA_WARSTWY_OSM = "db/dane/posrednie/osm_polska"
SCIEZKA_CECHY_OSM = "db/dane/gotowe/polska_cechy_osm"
LICZ_OSM = False

TEST_OD = "2025-01-01"
SCIEZKA_PELNE_CECHY = "db/dane/gotowe/polska_pelne_cechy"
LICZ_POZOSTALE_CECHY = False

SCIEZKA_AUDYT = "db/dane/gotowe/audyt_modelu"
WALIDACJA_OD = "2024-01-01"
AUDYTUJ_DANE = True

POSTGRES_HOST = "127.0.0.1"
# Plik .env leży w katalogu głównym, obok docker-compose.yml.
POSTGRES_ENV = "../.env"
POSTGRES_PARTIA = 25000
SCIEZKA_RAPORT_IMPORTU = "db/dane/posrednie/import_postgis.json"

# Trening modeli do wyceny. Progi cen liczone tylko na treningu.
TRENUJ_MODELE = False
SCIEZKA_MODELU = "db/dane/gotowe/model"
WARIANT_MODELU = "formularz"
CENA_M2_KWANTYL_DOL = 0.001
CENA_M2_KWANTYL_GORA = 0.998

# Serwer wyceny dla panelu.
API_PORT = 8000

# Testy w terminalu: zgodność cech panelu z ETL.
SPRAWDZ_CECHY_LICZBA = 1000
SCIEZKA_SPRAWDZENIA_CECH = "db/dane/gotowe/sprawdzenie_cech.json"

# Ważność permutacyjna przy treningu: wielkość próbki testu i liczba przetasowań.
WAZNOSC_PROBKA = 20000
WAZNOSC_POWTORZENIA = 3

# Eksperymenty z wyborem cech: python -m model.eksperyment.
# Uczą na sprzedażach przed WALIDACJA_OD, oceniają na walidacji (do TEST_OD); test zostaje nietknięty.
# EKSPERYMENT_SERIA: None = jeden eksperyment z ustawień poniżej,
# "grupy" = wszystkie cechy, a potem po kolei bez każdej grupy,
# "liczba_cech" = tylko N najważniejszych cech dla każdego N z EKSPERYMENT_LICZBY_CECH.
# Grupy: sasiedztwo, transakcja, lokalizacja, polozenie, czas, osm, przeznaczenie.
EKSPERYMENT_SERIA = None
EKSPERYMENT_NAZWA = "wszystkie"
EKSPERYMENT_POMIN_GRUPY = []
EKSPERYMENT_POMIN_CECHY = []
EKSPERYMENT_TYLKO_CECHY = None
EKSPERYMENT_LICZBY_CECH = [5, 10, 20, 40]
EKSPERYMENT_MODELE = ["Gradient Boosting"]
SCIEZKA_EKSPERYMENTOW = "db/dane/gotowe/eksperymenty"

# Wycena działek z pliku: python -m model.wycen_przyklady.
SCIEZKA_PRZYKLADOW = "przyklady.json"

# Backtest: wycena prawdziwych sprzedaży z testu pełną ścieżką panelu (python -m model.backtest).
BACKTEST_LICZBA = 2000
SCIEZKA_BACKTESTU = "db/dane/gotowe/backtest"
