from fractions import Fraction

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

import config
from etl.etap3_granice.granice import otworz_cache
from etl.etap2_4_czyszczenie.geometria import dodaj_geometrie

WOJEWODZTWA = ["02", "04", "06", "08", "10", "12", "14", "16", "18", "20", "22", "24", "26", "28", "30", "32"]

LEKKIE_KOLUMNY = [
    "tran_przestrzen_nazw",
    "tran_lokalny_id_iip",
    "tran_wersja_id",
    "dzi_id_dzialki",
    "dok_data",
    "nier_rodzaj",
    "tran_rodzaj_trans",
    "tran_cena_brutto",
    "nier_cena_brutto",
    "dzi_cena_brutto",
    "nier_udzial",
]

NOWE_KOLUMNY = [
    "teryt_woj",
    "teryt_powiat",
    "teryt_gmina",
    "teryt_obreb",
    "status_udzialu",
    "udzial_sprzedany",
    "klucz_transakcji",
]


def udzial_jako_liczba(tekst):
    if pd.isna(tekst):
        return None

    tekst = "".join(str(tekst).split()).rstrip(";").replace(",", ".")
    if tekst == "" or ";" in tekst:
        return None

    try:
        udzial = Fraction(tekst)
    except (ValueError, ZeroDivisionError):
        return None

    if udzial <= 0 or udzial > 1:
        return None
    return float(udzial)


def oczysc(wejscie, wyjscie):
    lejek = []

    print("KROK 1. Wczytanie lekkich kolumn całego RCN (bez geometrii)")
    dane = pd.read_parquet(wejscie, columns=LEKKIE_KOLUMNY)
    lejek.append(("wszystkie wiersze RCN", len(dane)))
    print(f"  wierszy: {len(dane):,}")

    print("KROK 2. Klucz transakcji: urząd + numer transakcji")
    for kolumna in ["tran_przestrzen_nazw", "tran_lokalny_id_iip", "tran_wersja_id", "dzi_id_dzialki"]:
        dane[kolumna] = dane[kolumna].fillna("").astype(str).str.strip()
    dane = dane[(dane["tran_przestrzen_nazw"] != "") & (dane["tran_lokalny_id_iip"] != "")].copy()
    dane["klucz_transakcji"] = dane["tran_przestrzen_nazw"] + "|" + dane["tran_lokalny_id_iip"]
    lejek.append(("ma klucz transakcji", len(dane)))
    print(f"  zostało: {len(dane):,}")

    print("KROK 3. Transakcje z kilkoma wersjami wpisu")
    wersje = dane.groupby("klucz_transakcji")["tran_wersja_id"].nunique()
    zle = wersje[wersje > 1].index
    dane = dane[~dane["klucz_transakcji"].isin(zle)]
    lejek.append(("jedna wersja wpisu", len(dane)))
    print(f"  zostało: {len(dane):,}")

    print("KROK 4. Transakcje, w których brakuje numeru działki")
    bez_dzialki = dane[dane["dzi_id_dzialki"] == ""]["klucz_transakcji"].unique()
    dane = dane[~dane["klucz_transakcji"].isin(bez_dzialki)]
    lejek.append(("każdy wiersz ma numer działki", len(dane)))
    print(f"  zostało: {len(dane):,}")

    # Jedna cena za kilka działek: nie wiadomo, ile kosztowała każda z nich.
    print("KROK 5. Transakcje obejmujące kilka działek")
    dzialki = dane.groupby("klucz_transakcji")["dzi_id_dzialki"].nunique()
    zle = dzialki[dzialki > 1].index
    dane = dane[~dane["klucz_transakcji"].isin(zle)]
    lejek.append(("jedna działka w transakcji", len(dane)))
    print(f"  zostało: {len(dane):,}")

    # Transakcja z kilkoma wierszami: wszystkie muszą być identyczne, inaczej nie wiadomo, który jest prawdziwy.
    print("KROK 6. Transakcje ze sprzecznymi wpisami (ten sam klucz, inne dane)")
    wiersze_w_transakcji = dane["klucz_transakcji"].value_counts()
    kilka_wierszy = wiersze_w_transakcji[wiersze_w_transakcji > 1].index
    do_sprawdzenia = dane[dane["klucz_transakcji"].isin(kilka_wierszy)]

    wszystkie_kolumny = []
    for nazwa in pq.ParquetFile(wejscie).schema_arrow.names:
        if nazwa not in ["gid", "geometry_bbox", "serwis_rcn"]:
            wszystkie_kolumny.append(nazwa)

    kawalki = []
    pozycja = 0
    for partia in pq.ParquetFile(wejscie).iter_batches(batch_size=config.WIELKOSC_PARTII, columns=wszystkie_kolumny):
        partia = partia.to_pandas()
        partia.index = range(pozycja, pozycja + len(partia))
        pozycja += len(partia)
        kawalki.append(partia[partia.index.isin(do_sprawdzenia.index)])
    cale_wiersze = pd.concat(kawalki)

    for kolumna in ["tran_przestrzen_nazw", "tran_lokalny_id_iip", "tran_wersja_id", "dzi_id_dzialki", "klucz_transakcji"]:
        cale_wiersze[kolumna] = do_sprawdzenia[kolumna]

    rozne_wpisy = cale_wiersze.drop_duplicates().groupby("klucz_transakcji").size()
    zle = rozne_wpisy[rozne_wpisy > 1].index
    dane = dane[~dane["klucz_transakcji"].isin(zle)]
    lejek.append(("wpisy transakcji zgodne", len(dane)))
    print(f"  zostało: {len(dane):,}")

    print("KROK 7. Powtórzone wiersze tej samej transakcji (zostaje pierwszy)")
    dane = dane.drop_duplicates(subset="klucz_transakcji", keep="first")
    lejek.append(("bez powtórzeń", len(dane)))
    print(f"  zostało: {len(dane):,}")

    print("KROK 8. Identyfikator działki i kody TERYT")
    czesci = dane["dzi_id_dzialki"].str.extract(r"^(\d{2})(\d{2})(\d{2})_([1-9])\.(\d{4})\.(\S+)$")
    dane["teryt_woj"] = czesci[0]
    dane["teryt_powiat"] = czesci[0] + czesci[1]
    dane["teryt_gmina"] = czesci[0] + czesci[1] + czesci[2] + czesci[3]
    dane["teryt_obreb"] = czesci[0] + czesci[1] + czesci[2] + "_" + czesci[3] + "." + czesci[4]
    dane = dane[dane["teryt_woj"].isin(WOJEWODZTWA)]
    if config.WOJEWODZTWO is not None:
        dane = dane[dane["teryt_woj"] == config.WOJEWODZTWO]
    lejek.append(("poprawny identyfikator działki", len(dane)))
    print(f"  zostało: {len(dane):,}")

    print("KROK 9. Data sprzedaży")
    dane = dane[dane["dok_data"].notna()]
    lejek.append(("jest data", len(dane)))
    dane = dane[dane["dok_data"].dt.normalize() <= pd.Timestamp(config.DATA_DO)]
    lejek.append(("data nie z przyszłości", len(dane)))
    dane = dane[dane["dok_data"].dt.year >= config.ROK_OD]
    lejek.append((f"data od {config.ROK_OD} roku", len(dane)))
    print(f"  zostało: {len(dane):,}")

    print("KROK 10. Tylko grunty niezabudowane")
    dane = dane[dane["nier_rodzaj"] == "nieruchomoscGruntowaNiezabudowana"]
    lejek.append(("grunt niezabudowany", len(dane)))
    print(f"  zostało: {len(dane):,}")

    print("KROK 11. Tylko wolny rynek")
    dane = dane[dane["tran_rodzaj_trans"] == "wolnyRynek"]
    lejek.append(("wolny rynek", len(dane)))
    print(f"  zostało: {len(dane):,}")

    print("KROK 12. Cena transakcji")
    cena = dane["tran_cena_brutto"]
    dane = dane[np.isfinite(cena) & (cena > 0)]
    lejek.append(("jest dodatnia cena", len(dane)))

    # Jeśli podano cenę nieruchomości albo działki, musi być równa cenie całej transakcji.
    zgodne = pd.Series(True, index=dane.index)
    for kolumna in ["nier_cena_brutto", "dzi_cena_brutto"]:
        podana = dane[kolumna].notna() & (dane[kolumna] != 0)
        rowna = (dane[kolumna] - dane["tran_cena_brutto"]).abs() <= 0.01
        zgodne = zgodne & (~podana | rowna)
    dane = dane[zgodne]
    lejek.append(("ceny składowe zgodne", len(dane)))
    print(f"  zostało: {len(dane):,}")

    print("KROK 13. Sprzedany udział ")
    udzialy = {}
    for tekst in dane["nier_udzial"].dropna().unique():
        udzialy[tekst] = udzial_jako_liczba(tekst)
    dane["udzial_sprzedany"] = dane["nier_udzial"].map(udzialy).astype(float)
    dane = dane[dane["udzial_sprzedany"].notna()].copy()
    dane["status_udzialu"] = np.where(dane["udzial_sprzedany"] == 1, "pelny", "czesciowy")
    lejek.append(("znany udział", len(dane)))
    print(f"  zostało: {len(dane):,}")

    print("KROK 14. Dociągnięcie wszystkich kolumn i geometrii dla zostałych wierszy")
    kawalki = []
    pozycja = 0
    for partia in pq.ParquetFile(wejscie).iter_batches(batch_size=config.WIELKOSC_PARTII, columns=config.KOLUMNY_POTRZEBNE):
        partia = partia.to_pandas()
        partia.index = range(pozycja, pozycja + len(partia))
        pozycja += len(partia)
        kawalki.append(partia[partia.index.isin(dane.index)])
    pelne = pd.concat(kawalki)

    pelne["dzi_id_dzialki"] = dane["dzi_id_dzialki"]
    for kolumna in NOWE_KOLUMNY:
        pelne[kolumna] = dane[kolumna]
    print(f"  wierszy: {len(pelne):,}")

    print("KROK 15. Granica działki, pole, środek i sprawdzenie powierzchni")
    baza_granic = otworz_cache(config.SCIEZKA_ULDK_GRANICE)
    pelne = dodaj_geometrie(pelne, baza_granic)
    baza_granic.close()

    print("KROK 16. Cena za metr i oznaczenie, czy działka nadaje się do modelu")
    pelne["cena_m2"] = pelne["tran_cena_brutto"] / (pelne["powierzchnia_m2"] * pelne["udzial_sprzedany"])
    pelne["cena_m2"] = pelne["cena_m2"].where(np.isfinite(pelne["cena_m2"]))

    ma_powierzchnie = pelne["powierzchnia_m2"] > 0
    w_zakresie = pelne["powierzchnia_m2"].between(config.POWIERZCHNIA_MIN, config.POWIERZCHNIA_MAX)
    pelne["do_modelu"] = ma_powierzchnie & w_zakresie & pelne["cena_m2"].notna()
    pelne["rok"] = pelne["dok_data"].dt.year.astype("int32")
    print(f"  do modelu: {pelne['do_modelu'].sum():,} z {len(pelne):,}")

    print("KROK 17. Zapis")
    kolumny = config.KOLUMNY_POTRZEBNE + NOWE_KOLUMNY + [
        "zrodlo_geometrii",
        "zrodlo_powierzchni",
        "pole_geom_m2",
        "obwod_m",
        "x_2180",
        "y_2180",
        "powierzchnia_m2",
        "cena_m2",
        "do_modelu",
        "rok",
    ]
    pelne[kolumny].to_parquet(wyjscie, index=False)
    print(f"  zapisano: {wyjscie}")

    print("\nLejek czyszczenia:")
    print(f"{'Krok':<34} {'Zostało':>12} {'Odpadło':>12}")
    poprzednio = lejek[0][1]
    for nazwa, zostalo in lejek:
        print(f"{nazwa:<34} {zostalo:>12,} {poprzednio - zostalo:>12,}")
        poprzednio = zostalo
