# Podglad gotowego zbioru: python zobacz.py

import pandas as pd

import config

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)


def wczytaj():
    return pd.read_parquet(f"{config.SCIEZKA_GOTOWE}/dane_z_cechami.parquet")


def podstawy(df):
    print()
    print("CO JEST W PLIKU")
    print("-" * 78)
    print(f"Transakcji: {len(df):,}")
    print(f"Kolumn:     {len(df.columns)}")
    print(f"Rozmiar w pamieci: {df.memory_usage(deep=True).sum() / 1024 / 1024:.0f} MB")


def jakie_kolumny(df):
    print()
    print("KOLUMNY")
    print("-" * 78)

    przeznaczenia = [k for k in df.columns if k.startswith("przezn_")]
    reszta = [k for k in df.columns if not k.startswith("przezn_")]

    print("Cechy i dane transakcji:")
    for i, nazwa in enumerate(reszta):
        print(f"   {nazwa:<24}", end="")
        if i % 3 == 2:
            print()
    print()

    print(f"\nPlus {len(przeznaczenia)} kolumn 0/1 z przeznaczeniem w planie miejscowym.")


def przyklady(df, ile=8):
    print()
    print(f"{ile} LOSOWYCH TRANSAKCJI")
    print("-" * 78)

    kolumny = [
        "data_transakcji", "miejscowosc", "powierzchnia_m2",
        "cena_brutto", "cena_m2", "sposob_uzytkowania",
    ]

    proba = df.sample(ile, random_state=42)[kolumny]
    print(proba.to_string(index=False))


def ceny(df):
    print()
    print("CENY ZA METR KWADRATOWY")
    print("-" * 78)

    opis = df["cena_m2"].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95])
    for nazwa, wartosc in opis.items():
        print(f"  {nazwa:<8} {wartosc:>10.2f}")

    print()
    print("Wedlug sposobu uzytkowania:")
    wedlug = df.groupby("sposob_uzytkowania")["cena_m2"].agg(["count", "median", "mean"])
    wedlug = wedlug.sort_values("count", ascending=False)

    for uzytek, wiersz in wedlug.iterrows():
        print(f"  {uzytek:<32} {int(wiersz['count']):>7,} szt.   "
              f"mediana {wiersz['median']:>7.2f}   srednia {wiersz['mean']:>8.2f}")


def najdrozsze_i_najtansze(df, ile=5):
    print()
    print(f"{ile} NAJDROZSZYCH DZIALEK (za metr)")
    print("-" * 78)

    kolumny = ["miejscowosc", "powierzchnia_m2", "cena_brutto", "cena_m2", "sposob_uzytkowania"]
    print(df.nlargest(ile, "cena_m2")[kolumny].to_string(index=False))

    print()
    print(f"{ile} NAJTANSZYCH DZIALEK (za metr)")
    print("-" * 78)
    print(df.nsmallest(ile, "cena_m2")[kolumny].to_string(index=False))


def gdzie_najwiecej(df, ile=15):
    print()
    print(f"{ile} GMIN Z NAJWIEKSZA LICZBA TRANSAKCJI")
    print("-" * 78)

    wedlug_gminy = df.groupby("teryt_gmina").agg(
        transakcji=("cena_m2", "size"),
        mediana_ceny=("cena_m2", "median"),
        mediana_powierzchni=("powierzchnia_m2", "median"),
    )
    wedlug_gminy = wedlug_gminy.sort_values("transakcji", ascending=False).head(ile)

    print(f"  {'gmina':<10} {'transakcji':>11} {'mediana zl/m2':>15} {'mediana m2':>12}")
    for gmina, wiersz in wedlug_gminy.iterrows():
        print(f"  {gmina:<10} {int(wiersz['transakcji']):>11,} "
              f"{wiersz['mediana_ceny']:>15.2f} {wiersz['mediana_powierzchni']:>12,.0f}")


def przeznaczenia(df):
    print()
    print("PRZEZNACZENIE W PLANIE MIEJSCOWYM")
    print("-" * 78)

    kolumny = [k for k in df.columns if k.startswith("przezn_")]
    sumy = df[kolumny].sum().sort_values(ascending=False)

    for nazwa, ile in sumy.items():
        etykieta = nazwa.replace("przezn_", "")
        print(f"  {etykieta:<46} {int(ile):>7,}  ({100 * ile / len(df):5.1f}%)")


def braki(df):
    print()
    print("CZEGO BRAKUJE")
    print("-" * 78)

    puste = df.isna().sum()
    puste = puste[puste > 0].sort_values(ascending=False)

    if len(puste) == 0:
        print("  Nic nie brakuje.")
        return

    for nazwa, ile in puste.items():
        print(f"  {nazwa:<24} brakuje {ile:>7,}  ({100 * ile / len(df):5.1f}%)")


def lejek():
    print()
    print("ILE ODPADLO NA KAZDYM KROKU CZYSZCZENIA")
    print("-" * 78)

    raport = pd.read_csv(f"{config.SCIEZKA_GOTOWE}/raport_czyszczenia.csv")

    for _, wiersz in raport.iterrows():
        odpada = "-" if wiersz["krok"] == 0 else f"{wiersz['odpada']:,}"
        print(f"  {wiersz['krok']:>2}. {wiersz['opis']:<38} "
              f"zostaje {wiersz['zostaje']:>9,}   odpada {odpada:>9}")


df = wczytaj()

podstawy(df)
jakie_kolumny(df)
przyklady(df)
ceny(df)
najdrozsze_i_najtansze(df)
gdzie_najwiecej(df)
przeznaczenia(df)
braki(df)
lejek()

print()
