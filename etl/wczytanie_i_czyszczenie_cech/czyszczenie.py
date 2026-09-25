import os

import config
from etl.wczytanie_i_czyszczenie_cech import raport

    # Identyfikator dzialki wyglada tak: 021001_1.0005.AR_17.35/2
    #                                    |  |  |  | |    |
    #                                    |  |  |  | |    numer dzialki
    #                                    |  |  |  | obreb ewidencyjny
    #                                    |  |  |  typ gminy
    #                                    |  |  gmina
    #                                    |  powiat
    #                                    wojewodztwo

def rozbij_identyfikator(df):
    czesci = df["dzi_id_dzialki"].str.extract(
        r"^(\d{2})(\d{2})(\d{2})_(\w)\.(\d{4})\.(.+)$"
    )
    czesci.columns = ["woj", "pow", "gm", "typ", "obreb", "nr"]

    df["teryt_woj"] = czesci["woj"]
    df["teryt_powiat"] = czesci["woj"] + czesci["pow"]
    df["teryt_gmina"] = czesci["woj"] + czesci["pow"] + czesci["gm"]

    return df


def krok_01_ma_identyfikator(df):

    przed = len(df)

    ma = df["dzi_id_dzialki"].notna()
    raport.zapisz_odrzucone(df[~ma], "krok_01_brak_identyfikatora")
    df = df[ma].copy()

    raport.zanotuj(1, "ma identyfikator dzialki", len(df), przed - len(df))
    return df


def krok_02_format_identyfikatora(df):
    # Uszkodzony identyfikator nie rozklada sie na czesci. Pusty wojewodztwo znaczy, ze reszta tez.
    przed = len(df)

    df = rozbij_identyfikator(df)

    dobry = df["teryt_woj"].notna()
    raport.zapisz_odrzucone(df[~dobry], "krok_02_uszkodzony_identyfikator")
    df = df[dobry].copy()

    raport.zanotuj(2, "identyfikator w poprawnym formacie", len(df), przed - len(df))
    return df


def krok_03_wojewodztwo(df):
    # Zostawiam tylko wojewodztwo 02. 
    przed = len(df)

    czy_dolnoslaskie = df["teryt_woj"] == config.WOJEWODZTWO
    raport.zapisz_odrzucone(df[~czy_dolnoslaskie], "krok_03_obce_wojewodztwo")
    df = df[czy_dolnoslaskie].copy()

    raport.zanotuj(3, "wojewodztwo dolnoslaskie", len(df), przed - len(df))
    return df


def krok_04_ma_date(df):

    przed = len(df)

    brakuje = df["dok_data"].isna()
    raport.zapisz_odrzucone(df[brakuje], "krok_04_brak_daty")
    df = df[~brakuje].copy()

    raport.zanotuj(4, "ma date dokumentu", len(df), przed - len(df))
    return df


def krok_05_data_sensowna(df):
    # Odcinam daty spoza realnego zakresu lat. 
    przed = len(df)

    df["rok"] = df["dok_data"].dt.year
    bez_sensu = (df["rok"] < config.ROK_MIN_SENSOWNY) | (df["rok"] > config.ROK_MAX_SENSOWNY)

    raport.zapisz_odrzucone(df[bez_sensu], "krok_05_data_bez_sensu")
    df = df[~bez_sensu].copy()

    raport.zanotuj(5, f"data sensowna ({config.ROK_MIN_SENSOWNY}-{config.ROK_MAX_SENSOWNY})", len(df), przed - len(df))
    return df


def krok_06_dzialka_niezabudowana(df):
    # Tylko grunt niezabudowany. Przy budynku cena nie jest cena dzialki.
    przed = len(df)

    czy_niezabudowana = df["nier_rodzaj"] == "nieruchomoscGruntowaNiezabudowana"
    raport.zapisz_odrzucone(df[~czy_niezabudowana], "krok_06_inny_rodzaj_nieruchomosci")
    df = df[czy_niezabudowana].copy()

    raport.zanotuj(6, "nieruchomosc gruntowa niezabudowana", len(df), przed - len(df))
    return df


def krok_07_wolny_rynek(df):
    # Tylko wolny rynek. Sprzedaz z bonifikata znieksztalca cene.
    przed = len(df)

    czy_wolny = df["tran_rodzaj_trans"] == "wolnyRynek"
    raport.zapisz_odrzucone(df[~czy_wolny], "krok_07_nie_wolny_rynek")
    df = df[czy_wolny].copy()

    raport.zanotuj(7, "wolny rynek", len(df), przed - len(df))
    return df


def krok_08_jedna_dzialka(df):
    # Przy kilku dzialkach w jednej transakcji nie wiadomo, ile kosztowala kazda. 
    przed = len(df)

    pogrupowane = df.groupby("tran_lokalny_id_iip")
    wybrana_kolumna = pogrupowane["tran_lokalny_id_iip"]
    rozmiary = wybrana_kolumna.transform("size")
    df["liczba_dzialek"] = rozmiary

    wiele = df["liczba_dzialek"] > 1
    raport.zapisz_odrzucone(df[wiele], "krok_08_wiele_dzialek_w_transakcji")
    df = df[~wiele].copy()
    df = df.drop(columns=["liczba_dzialek"])

    raport.zanotuj(8, "transakcja z jedna dzialka", len(df), przed - len(df))
    return df


def krok_09_od_roku(df):
    # Starsze ceny slabo opisuja obecny rynek.
    przed = len(df)

    stare = df["rok"] < config.ROK_OD
    raport.zapisz_odrzucone(df[stare], "krok_09_za_stare")
    df = df[~stare].copy()

    raport.zanotuj(9, f"od {config.ROK_OD} roku", len(df), przed - len(df))
    return df


def krok_10_cena_sensowna(df):
    # Bardzo niska cena czesto nie jest sprzedaza rynkowa. 
    przed = len(df)

    za_tanie = df["tran_cena_brutto"].isna() | (df["tran_cena_brutto"] <= config.CENA_MIN)
    raport.zapisz_odrzucone(df[za_tanie], "krok_10_cena_za_niska")
    df = df[~za_tanie].copy()

    raport.zanotuj(10, f"cena powyzej {config.CENA_MIN} zl", len(df), przed - len(df))
    return df


def krok_11_ma_powierzchnie(df):
    przed = len(df)

    brakuje = df["dzi_pow_ewid"].isna() | (df["dzi_pow_ewid"] <= 0)
    raport.zapisz_odrzucone(df[brakuje], "krok_11_brak_powierzchni")
    df = df[~brakuje].copy()

    raport.zanotuj(11, "ma powierzchnie", len(df), przed - len(df))
    return df


def krok_12_bez_duplikatow(df):
    # Ten sam identyfikator transakcji potrafi wejsc do pliku wiecej niz raz.
    przed = len(df)

    duplikat = df.duplicated("tran_lokalny_id_iip")
    raport.zapisz_odrzucone(df[duplikat], "krok_12_duplikaty")
    df = df[~duplikat].copy()

    raport.zanotuj(12, "bez duplikatow", len(df), przed - len(df))
    return df


def krok_13_powierzchnia_w_zakresie(df):
    # Ponizej 100 m2 to zwykle udzialy w dojazdach, powyzej 20 ha inna logika cenowa.
    przed = len(df)

    poza = (df["powierzchnia_m2"] < config.POWIERZCHNIA_MIN) | (df["powierzchnia_m2"] > config.POWIERZCHNIA_MAX)
    raport.zapisz_odrzucone(df[poza], "krok_13_powierzchnia_poza_zakresem")
    df = df[~poza].copy()

    raport.zanotuj(13, "powierzchnia 100 m2 - 20 ha", len(df), przed - len(df))
    return df


def krok_14_cena_za_metr(df):
    # Odcinam oczywiste bledy ceny za metr.
    przed = len(df)

    df["cena_m2"] = df["tran_cena_brutto"] / df["powierzchnia_m2"]

    poza = (df["cena_m2"] < config.CENA_M2_MIN) | (df["cena_m2"] > config.CENA_M2_MAX)
    raport.zapisz_odrzucone(df[poza], "krok_14_cena_za_metr_poza_zakresem")
    df = df[~poza].copy()

    raport.zanotuj(14, "cena za m2 w rozsadnym zakresie", len(df), przed - len(df))
    return df


def krok_15_odstajace_w_grupach(df):
    # Percentyle licze w grupie uzytkowanie x powiat, bo ceny grup roznia sie mocno.
    przed = len(df)

    df["do_usuniecia"] = False

    for grupa, dane in df.groupby(["dzi_sposob_uzyt", "teryt_powiat"]):
        if len(dane) < config.MIN_LICZEBNOSC_GRUPY:
            continue

        dol = dane["cena_m2"].quantile(config.PERCENTYL_DOL)
        gora = dane["cena_m2"].quantile(config.PERCENTYL_GORA)

        odstaje = (dane["cena_m2"] < dol) | (dane["cena_m2"] > gora)
        df.loc[dane[odstaje].index, "do_usuniecia"] = True

    # Male grupy dostaja progi liczone tylko po uzytkowaniu.
    male = df.groupby(["dzi_sposob_uzyt", "teryt_powiat"]).transform("size") < config.MIN_LICZEBNOSC_GRUPY

    for uzytek, dane in df[male].groupby("dzi_sposob_uzyt"):
        if len(dane) < config.MIN_LICZEBNOSC_GRUPY:
            continue

        dol = dane["cena_m2"].quantile(config.PERCENTYL_DOL)
        gora = dane["cena_m2"].quantile(config.PERCENTYL_GORA)

        odstaje = (dane["cena_m2"] < dol) | (dane["cena_m2"] > gora)
        df.loc[dane[odstaje].index, "do_usuniecia"] = True
    
    do_usuniecia = df["do_usuniecia"]
    raport.zapisz_odrzucone(df[do_usuniecia], "krok_15_wartosci_odstajace")
    df = df[~do_usuniecia].copy()
    df = df.drop(columns=["do_usuniecia"])

    raport.zanotuj(15, "bez wartosci odstajacych w grupach", len(df), przed - len(df))
    return df


def wyczysc(df):
    raport.naglowek_lejka(len(df))

    df = krok_01_ma_identyfikator(df)
    df = krok_02_format_identyfikatora(df)
    df = krok_03_wojewodztwo(df)
    df = krok_04_ma_date(df)
    df = krok_05_data_sensowna(df)
    df = krok_06_dzialka_niezabudowana(df)
    df = krok_07_wolny_rynek(df)
    df = krok_08_jedna_dzialka(df)
    df = krok_09_od_roku(df)
    df = krok_10_cena_sensowna(df)
    df = krok_11_ma_powierzchnie(df)
    df = krok_12_bez_duplikatow(df)

    sciezka = os.path.join(config.SCIEZKA_POSREDNIE, "02_oczyszczone.parquet")
    df.to_parquet(sciezka, index=False)

    return df


def dokoncz_czyszczenie(df):

    df = krok_13_powierzchnia_w_zakresie(df)
    df = krok_14_cena_za_metr(df)
    df = krok_15_odstajace_w_grupach(df)

    raport.zapisz_raport()

    return df
