import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

KOLUMNY = [
    "mediana_cena_m2_2km_ten_sam_uzytek",
    "mediana_cena_m2_2km_24m",
    "mediana_cena_m2_5km_24m",
    "mediana_cena_m2_obreb",
    "mediana_cena_m2_gmina",
    "liczba_transakcji_2km_24m",
]


def dodaj_sasiedztwo_cenowe(dane):
    print()
    print("SASIADZTWO CENOWE")
    print("-" * 78)

    for kolumna in KOLUMNY:
        dane[kolumna] = np.nan

    if "cena_m2" not in dane.columns or "data_transakcji" not in dane.columns:
        print("  brak ceny albo daty, cechy puste")
        return dane

    dopisz_mediane_grupy(dane, dane["teryt_gmina"], "mediana_cena_m2_gmina")
    dopisz_mediane_grupy(
        dane, obreb_z_identyfikatora(dane["dzi_id_dzialki"]), "mediana_cena_m2_obreb"
    )
    dopisz_sasiedztwo_na_mapie(dane)

    print(
        f"  gmina wypelniona w {dane['mediana_cena_m2_gmina'].notna().sum():,} wierszach"
    )
    return dane


def obreb_z_identyfikatora(identyfikatory):

    return identyfikatory.str.extract(r"^(\d{6}_\w\.\d{4})", expand=False)


def dopisz_mediane_grupy(dane, grupy, nazwa_cechy):
    ramka = pd.DataFrame(
        {
            "grupa": grupy,
            "data": dane["data_transakcji"],
            "cena": dane["cena_m2"],
        }
    )
    ramka = ramka.dropna(subset=["grupa", "data", "cena"])

    for _, czesc in ramka.groupby("grupa"):
        czesc = czesc.sort_values("data")
        daty = czesc["data"].to_numpy()
        ceny = czesc["cena"].to_numpy()
        for data in pd.unique(daty):
            mediana = mediana_przed(daty, ceny, data, None)
            wiersze = czesc.index[daty == czas(data)]
            dane.loc[wiersze, nazwa_cechy] = mediana


def mediana_przed(daty, ceny, do_daty, od_daty):
    prawo = np.searchsorted(daty, czas(do_daty), side="left")
    lewo = 0
    if od_daty is not None:
        lewo = np.searchsorted(daty, czas(od_daty), side="left")
    if prawo <= lewo:
        return np.nan
    return float(np.median(ceny[lewo:prawo]))


def czas(wartosc):
    return np.datetime64(pd.Timestamp(wartosc).to_datetime64())


def dopisz_sasiedztwo_na_mapie(dane):
    ma_srodek = dane["x_2180"].notna() & dane["y_2180"].notna()
    if ma_srodek.sum() < 2:
        print("  za malo dzialek ze srodkiem")
        return

    czesc = dane.loc[ma_srodek].copy()
    xy = czesc[["x_2180", "y_2180"]].to_numpy()
    daty = czesc["data_transakcji"].to_numpy()
    ceny = czesc["cena_m2"].to_numpy()
    uzytki = czesc["sposob_uzytkowania"].to_numpy()
    od_24 = (czesc["data_transakcji"] - pd.DateOffset(months=24)).to_numpy()

    drzewo = cKDTree(xy)
    sasiedzi = drzewo.query_ball_point(xy, r=5000)

    med2 = np.full(len(czesc), np.nan)
    med2_uzytek = np.full(len(czesc), np.nan)
    med5 = np.full(len(czesc), np.nan)
    ile = np.full(len(czesc), np.nan)

    for i, lista in enumerate(sasiedzi):
        if len(lista) <= 1:
            continue

        indeksy = np.array([j for j in lista if j != i], dtype=int)
        wczesniej = daty[indeksy] < daty[i]
        if not wczesniej.any():
            continue

        indeksy = indeksy[wczesniej]
        roznica = xy[indeksy] - xy[i]
        dystans = np.sqrt((roznica**2).sum(axis=1))

        w_oknie = daty[indeksy] >= od_24[i]
        if not w_oknie.any():
            continue

        ceny_okna = ceny[indeksy][w_oknie]
        dystans_okna = dystans[w_oknie]
        med5[i] = np.median(ceny_okna)

        blisko = dystans_okna <= 2000
        if not blisko.any():
            continue

        med2[i] = np.median(ceny_okna[blisko])
        ile[i] = int(blisko.sum())
        ten_sam = uzytki[indeksy][w_oknie][blisko] == uzytki[i]
        if ten_sam.any():
            med2_uzytek[i] = np.median(ceny_okna[blisko][ten_sam])

    wiersze = czesc.index
    dane.loc[wiersze, "mediana_cena_m2_2km_24m"] = med2
    dane.loc[wiersze, "mediana_cena_m2_2km_ten_sam_uzytek"] = med2_uzytek
    dane.loc[wiersze, "mediana_cena_m2_5km_24m"] = med5
    dane.loc[wiersze, "liczba_transakcji_2km_24m"] = ile
