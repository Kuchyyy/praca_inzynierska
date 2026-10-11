import numpy as np


def dodaj_powierzchnie(df):
    df["log_powierzchnia"] = np.log(df["powierzchnia_m2"])
    return df


def dodaj_przeznaczenie(df):
    # W dzi_przezn_wmpzp kilka przeznaczen jest rozdzielonych srednikiem.
    # Kazde dostaje osobna kolumne 0/1.
    wypelnione = df["dzi_przezn_wmpzp"].notna()

    rozbite = df.loc[wypelnione, "dzi_przezn_wmpzp"].str.split(";")
    wszystkie = sorted(set(rozbite.explode().str.strip()))

    print(f"  znaleziono {len(wszystkie)} kategorii przeznaczenia w planie miejscowym")

    zbiory = (
        df["dzi_przezn_wmpzp"]
        .fillna("")
        .apply(
            lambda tekst: (
                set(czesc.strip() for czesc in tekst.split(";")) if tekst else set()
            )
        )
    )

    for kategoria in wszystkie:
        nazwa_kolumny = "przezn_" + kategoria
        df[nazwa_kolumny] = zbiory.apply(lambda zbior: 1 if kategoria in zbior else 0)

    # Brak wpisu zwykle oznacza grunt poza planem miejscowym.
    df["przezn_brak_danych"] = (~wypelnione).astype(int)

    # Czy dzialka w ogole ma plan miejscowy.
    ma_plan = wypelnione & (df["dzi_przezn_wmpzp"] != "brakMPZPLubWZ")
    df["ma_mpzp"] = ma_plan.astype(int)

    return df


def dodaj_czas(df):
    # Czas w miesiacach od 2015. Kwartal pomijam, bo nie daje stabilnej sezonowosci.
    df["miesiace_od_2015"] = (df["rok"] - 2015) * 12 + df["dok_data"].dt.month - 1

    return df


def dodaj_miejscowosc(df):
    # Z adresu MSC:Wroclaw;UL:... bierzemy tylko miejscowosc.
    df["miejscowosc"] = df["dzi_adres"].str.extract(r"MSC:([^;]+)")[0]
    df["miejscowosc"] = df["miejscowosc"].str.strip().str.upper()

    ile = df["miejscowosc"].notna().sum()
    print(
        f"  odczytano miejscowosc dla {ile:,} transakcji ({100 * ile / len(df):.1f}%)"
    )

    return df


def zmien_nazwy(df):
    # Skroty z pliku na czytelniejsze nazwy kolumn.
    df = df.rename(
        columns={
            "dzi_sposob_uzyt": "sposob_uzytkowania",
            "nier_prawo": "prawo",
            "tran_sprzedajacy": "sprzedajacy",
            "tran_cena_brutto": "cena_brutto",
            "dok_data": "data_transakcji",
            "tran_lokalny_id_iip": "id_transakcji",
        }
    )

    return df


def dodaj_cechy_podstawowe(df):
    print()
    print("CECHY PODSTAWOWE")
    print("-" * 78)

    df = dodaj_powierzchnie(df)
    df = dodaj_przeznaczenie(df)
    df = dodaj_czas(df)
    df = dodaj_miejscowosc(df)
    df = zmien_nazwy(df)

    print(f"  gmin w zbiorze:   {df['teryt_gmina'].nunique()}")
    print(f"  powiatow:         {df['teryt_powiat'].nunique()}")
    print(f"  miejscowosci:     {df['miejscowosc'].nunique()}")

    return df
