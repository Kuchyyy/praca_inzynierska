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
