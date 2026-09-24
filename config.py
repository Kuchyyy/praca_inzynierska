# Sciezki i progi. Zmiany ustawien robie tutaj.

SCIEZKA_SUROWE = "dane/surowe/02_transakcje_ceny_dzialki.parquet"
SCIEZKA_POSREDNIE = "dane/posrednie"
SCIEZKA_ODRZUCONE = "dane/posrednie/odrzucone"
SCIEZKA_GOTOWE = "dane/gotowe"


WOJEWODZTWO = "02"


ROK_OD = 2015

ROK_MIN_SENSOWNY = 1995
ROK_MAX_SENSOWNY = 2026

CENA_MIN = 1000


POWIERZCHNIA_MIN = 100
POWIERZCHNIA_MAX = 200000


CENA_M2_MIN = 1
CENA_M2_MAX = 5000

PROG_HEKTARY = 30

# Dopuszczalny stosunek powierzchni z pliku do pola z geometrii.
TOLERANCJA_POLA_DOL = 0.80
TOLERANCJA_POLA_GORA = 1.25


PERCENTYL_DOL = 0.01
PERCENTYL_GORA = 0.99

# Ponizej tej liczebnosci grupa nie dostaje wlasnych percentyli.
MIN_LICZEBNOSC_GRUPY = 50


KOLUMNY_POTRZEBNE = [
    "teryt",
    "tran_lokalny_id_iip",
    "tran_rodzaj_trans",
    "tran_sprzedajacy",
    "tran_cena_brutto",
    "dok_data",
    "nier_rodzaj",
    "nier_prawo",
    "dzi_id_dzialki",
    "dzi_przezn_wmpzp",
    "dzi_pow_ewid",
    "dzi_sposob_uzyt",
    "dzi_adres",
    "geometry",
]
