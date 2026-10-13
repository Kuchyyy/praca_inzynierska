import json
from datetime import date
from fractions import Fraction

import numpy as np
import pandas as pd

import config
from etl.wczytanie_i_czyszczenie_cech.geometria import dodaj_geometrie

WOJEWODZTWA = ["02", "04", "06", "08", "10", "12", "14", "16", "18", "20", "22", "24", "26", "28", "30", "32"]


def odfiltruj(df, zostaw, powod, liczniki):
    zostaw = zostaw.fillna(False)
    liczniki[powod] += int((~zostaw).sum())
    return df.loc[zostaw].copy()


def ocen_udzial(wartosc):
    if pd.isna(wartosc) or not str(wartosc).strip():
        return "brak"
    tekst = "".join(str(wartosc).split()).rstrip(";").replace(",", ".")
    if ";" in tekst:
        return "wiele_wpisow"
    try:
        udzial = Fraction(tekst)
    except (ValueError, ZeroDivisionError):
        return "niepoprawny"
    if udzial == 1:
        return "pelny"
    if 0 < udzial < 1:
        return "czesciowy"
    return "niepoprawny"


def wyczysc_partie(df, liczniki, baza_uldk):
    df = df.copy()
    df["dzi_id_dzialki"] = df["dzi_id_dzialki"].str.strip()
    czesci = df["dzi_id_dzialki"].str.extract(r"^(\d{2})(\d{2})(\d{2})_([1-9])\.(\d{4})\.(\S+)$")
    df["teryt_woj"] = czesci[0]
    df["teryt_powiat"] = czesci[0] + czesci[1]
    df["teryt_gmina"] = czesci[0] + czesci[1] + czesci[2] + czesci[3]
    df["teryt_obreb"] = czesci[0] + czesci[1] + czesci[2] + "_" + czesci[3] + "." + czesci[4]
    df = odfiltruj(df, df["teryt_woj"].isin(WOJEWODZTWA), "bledny_id_dzialki", liczniki)
    if config.WOJEWODZTWO is not None:
        df = odfiltruj(df, df["teryt_woj"].eq(config.WOJEWODZTWO), "inne_wojewodztwo", liczniki)

    data_do = date.fromisoformat(config.DATA_DO)
    df = odfiltruj(df, df["dok_data"].notna(), "brak_daty", liczniki)
    df = odfiltruj(df, df["dok_data"].dt.date.le(data_do), "data_z_przyszlosci", liczniki)
    df = odfiltruj(df, df["dok_data"].dt.year.ge(config.ROK_OD), "data_przed_zakresem", liczniki)
    df = odfiltruj(df, df["nier_rodzaj"].eq("nieruchomoscGruntowaNiezabudowana"), "inny_rodzaj_nieruchomosci", liczniki)
    df = odfiltruj(df, df["tran_rodzaj_trans"].eq("wolnyRynek"), "inny_rodzaj_transakcji", liczniki)

    udzialy = {w: ocen_udzial(w) for w in df["nier_udzial"].dropna().unique()}
    df["status_udzialu"] = df["nier_udzial"].map(udzialy).fillna("brak")

    cena = df["tran_cena_brutto"]
    df = odfiltruj(df, np.isfinite(cena) & cena.gt(0), "brak_lub_bledna_cena", liczniki)

    # Cena całego aktu nie może udawać ceny jednej działki.
    zgodne = pd.Series(True, index=df.index)
    for kolumna in ["nier_cena_brutto", "dzi_cena_brutto"]:
        podana = df[kolumna].notna() & df[kolumna].ne(0)
        rowna = np.isfinite(df[kolumna]) & (df[kolumna] - df["tran_cena_brutto"]).abs().le(0.01)
        zgodne &= ~podana | rowna
    df = odfiltruj(df, zgodne, "niezgodne_ceny_skladowe", liczniki)

    df = odfiltruj(df, df["status_udzialu"].isin(["pelny", "czesciowy"]), "nieznany_lub_bledny_udzial", liczniki)
    df["udzial_sprzedany"] = df["nier_udzial"].map(
        lambda w: float(Fraction("".join(str(w).split()).rstrip(";").replace(",", ".")))
    ).astype("float64")
    df = odfiltruj(df, np.isfinite(df["udzial_sprzedany"]) & df["udzial_sprzedany"].gt(0), "udzial_poza_precyzja", liczniki)

    df = dodaj_geometrie(df, baza_uldk)

    ma_powierzchnie = np.isfinite(df["powierzchnia_m2"]) & df["powierzchnia_m2"].gt(0)
    w_zakresie = df["powierzchnia_m2"].between(config.POWIERZCHNIA_MIN, config.POWIERZCHNIA_MAX)

    df["cena_m2"] = np.nan
    ceny = df.loc[ma_powierzchnie, "tran_cena_brutto"]
    powierzchnie = df.loc[ma_powierzchnie, "powierzchnia_m2"]
    udzialy = df.loc[ma_powierzchnie, "udzial_sprzedany"]
    df.loc[ma_powierzchnie, "cena_m2"] = ceny / (powierzchnie * udzialy)
    df["cena_m2"] = df["cena_m2"].where(np.isfinite(df["cena_m2"]))

    df["do_modelu"] = ma_powierzchnie & w_zakresie & df["cena_m2"].notna()
    df["rok"] = df["dok_data"].dt.year.astype("int32")
    df["klucz_transakcji"] = [
        json.dumps([str(p).strip(), str(i).strip()], ensure_ascii=False, separators=(",", ":"))
        for p, i in zip(df["tran_przestrzen_nazw"], df["tran_lokalny_id_iip"])
    ]
    return df
