import os

import pandas as pd

import config


kroki = []
powiaty_w_surowych = set()


def zanotuj(numer, opis, zostaje, odpada):
    kroki.append({
        "krok": numer,
        "opis": opis,
        "zostaje": zostaje,
        "odpada": odpada,
    })

    print(f"{numer:>3}. {opis:<38} zostaje {zostaje:>9,}   odpada {odpada:>9,}")


def naglowek_lejka(liczba_wierszy):
    print()
    print("CZYSZCZENIE DANYCH")
    print("-" * 78)
    print(f"{'  0':>3}. {'surowe wiersze':<38} zostaje {liczba_wierszy:>9,}   odpada {'-':>9}")

    kroki.append({
        "krok": 0,
        "opis": "surowe wiersze",
        "zostaje": liczba_wierszy,
        "odpada": 0,
    })


def zapisz_odrzucone(df_odrzucone, nazwa):
    # Geometria nie jest potrzebna do sprawdzenia, co odpadlo.
    if len(df_odrzucone) == 0:
        return

    kolumny = []
    for k in df_odrzucone.columns:
        if k != "geometry":
            kolumny.append(k)

    sciezka = os.path.join(config.SCIEZKA_ODRZUCONE, f"{nazwa}.parquet")
    df_odrzucone[kolumny].to_parquet(sciezka, index=False)


def zapisz_raport():
    raport = pd.DataFrame(kroki)
    sciezka = os.path.join(config.SCIEZKA_GOTOWE, "raport_czyszczenia.csv")
    raport.to_csv(sciezka, index=False)

    print("-" * 78)
    print(f"Raport z czyszczenia zapisany do {sciezka}")


def pokaz_podsumowanie(df):
    print()
    print("PODSUMOWANIE")
    print("-" * 78)
    print(f"Transakcji w gotowym zbiorze: {len(df):,}")
    print(f"Kolumn w gotowym zbiorze:     {len(df.columns)}")

    if "zrodlo_powierzchni" in df.columns:
        print()
        print("Skad wiemy, jaka jest powierzchnia dzialki:")
        for zrodlo, ile in df["zrodlo_powierzchni"].value_counts().items():
            print(f"  {zrodlo:<20} {ile:>8,}  ({100 * ile / len(df):5.1f}%)")

    print()
    print("Transakcje w latach:")
    for rok, ile in df["rok"].value_counts().sort_index().items():
        print(f"  {rok}  {ile:>7,}")

    if powiaty_w_surowych:
        zostaly = set(df["teryt_powiat"].unique())
        zgubione = sorted(powiaty_w_surowych - zostaly)

        print()
        print(f"Powiatow w surowym pliku: {len(powiaty_w_surowych)}, w gotowym zbiorze: {len(zostaly)}")

        if zgubione:
            print(f"UWAGA - powiaty, ktore wypadly w calosci: {', '.join(zgubione)}")
            print("       Najczestsza przyczyna to brak dat transakcji w danym powiecie.")

    gminy = df["teryt_gmina"].value_counts()
    print()
    print(f"Gmin w zbiorze:                {len(gminy)}")
    print(f"Mediana transakcji na gmine:   {int(gminy.median()):,}")
    print(f"Najmniej transakcji w gminie:  {gminy.min():,}")

    print()
    print("Cena za metr kwadratowy:")
    print(f"  mediana  {df['cena_m2'].median():8.2f} zl")
    print(f"  srednia  {df['cena_m2'].mean():8.2f} zl")

    print()
    print("Mediana ceny za m2 wedlug sposobu uzytkowania:")
    wedlug_uzytku = df.groupby("sposob_uzytkowania")["cena_m2"].agg(["count", "median"])
    wedlug_uzytku = wedlug_uzytku.sort_values("count", ascending=False)

    for uzytek, wiersz in wedlug_uzytku.iterrows():
        print(f"  {uzytek:<32} {int(wiersz['count']):>7,} szt.   {wiersz['median']:7.2f} zl/m2")

    print()
