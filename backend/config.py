SCIEZKA_SUROWE = "db/dane/surowe/rcn/0_transakcje_ceny_dzialki.parquet"
SCIEZKA_OSM = "db/dane/surowe/osm/poland-260930.osm.pbf"

SCIEZKA_OCZYSZCZONE = "db/dane/gotowe/polska_oczyszczone/transakcje.parquet"
SCIEZKA_ULDK_GRANICE = "db/dane/posrednie/uldk_granice.sqlite"
SCIEZKA_PACZKI_EGIB = "db/dane/posrednie/egib_paczki"
SCIEZKA_Z_GRANICAMI = "db/dane/gotowe/polska_po_egib/transakcje.parquet"
SCIEZKA_WARSTWY_OSM = "db/dane/posrednie/osm_polska"
SCIEZKA_CECHY_OSM = "db/dane/gotowe/polska_cechy_osm/transakcje.parquet"
SCIEZKA_PELNE_CECHY = "db/dane/gotowe/polska_pelne_cechy/transakcje.parquet"
SCIEZKA_MODELU = "db/dane/gotowe/model.joblib"

# Etapy, które pobierają dane z sieci, zapisują do bazy albo uczą modele, włączamy ręcznie.
UZUPELNIJ_ULDK = False
UZUPELNIJ_EGIB = False
IMPORTUJ_DO_BAZY = False
TRENUJ_MODELE = False
SYMULACJA_CECH = False
WALIDACJA_KROCZACA = False
WAZNOSC_CECH = False

DATA_DO = "2026-10-02"
ROK_OD = 2015
TEST_OD = "2025-01-01"
# Lata walidacji kroczącej (walidacja_kroczaca_modele.py): uczenie na latach wcześniejszych.
WALIDACJA_LATA = [2021, 2022, 2023, 2024]
WOJEWODZTWO = None
WIELKOSC_PARTII = 25000
PRZERWA_ULDK = 0.1

POWIERZCHNIA_MIN = 100
POWIERZCHNIA_MAX = 200000
TOLERANCJA_POLA_DOL = 0.80
TOLERANCJA_POLA_GORA = 1.25

# Kolumny czytane z RCN
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

CENA_M2_KWANTYL_DOL = 0.001
CENA_M2_KWANTYL_GORA = 0.998
WAZNOSC_PROBKA = 20000
WAZNOSC_POWTORZENIA = 3

# Baza działa lokalnie w Dockerze, bez haseł.
POSTGRES_HOST = "127.0.0.1"
POSTGRES_PORT = 5432
POSTGRES_DB = "dzialki"
API_PORT = 8000

# Eksperymenty z cechami: python eksperymenty_cech.py.
# Nazwa eksperymentu: co pomijamy. Można podać grupę (transakcja, lokalizacja, polozenie,
# czas, osm, przeznaczenie, sasiedztwo) albo pojedynczą cechę. Pusta lista = wszystkie cechy.
EKSPERYMENTY = {
    "wszystkie_cechy": [],
    "bez_osm": ["osm"],
    "bez_sasiedztwa": ["sasiedztwo"],
    "bez_przeznaczenia": ["przeznaczenie"],
    "bez_polozenia": ["polozenie"],
    "bez_czasu": ["czas"],
    "bez_lokalizacji": ["lokalizacja"],
    "bez_transakcji": ["transakcja"],
    "bez_osm_i_sasiedztwa": ["osm", "sasiedztwo"],
    "bez_odl_do_budynku": ["odl_najblizszy_budynek_m"],
    "bez_ksztaltu_dzialki": ["wskaznik_zwartosci"],
    "bez_wspolrzednych": ["x_2180", "y_2180"],
}
