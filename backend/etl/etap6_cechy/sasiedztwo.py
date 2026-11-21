import time

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

CECHY = [
    "mediana_cena_m2_2km_ten_sam_uzytek",
    "mediana_cena_m2_2km_24m",
    "mediana_cena_m2_5km_24m",
    "mediana_cena_m2_obreb",
    "mediana_cena_m2_gmina",
    "liczba_transakcji_2km_24m",
    "odl_najblizsza_transakcja_m",
]


def dodaj_sasiedztwo(dane, test_od):
    dane = dane.reset_index(drop=True).copy()

    dzien = dane["dok_data"].dt.normalize()
    daty = dzien.to_numpy()
    dwa_lata_wczesniej = (dzien - pd.DateOffset(months=24)).to_numpy()
    ceny = dane["cena_m2"].to_numpy()
    dzialki = dane["dzi_id_dzialki"].to_numpy()
    uzytki = dane["dzi_sposob_uzyt"].fillna("").to_numpy()
    xy = dane[["x_2180", "y_2180"]].to_numpy()

    dane["zbior"] = np.where(daty < np.datetime64(test_od), "trening", "test")
    trening = (dane["zbior"] == "trening").to_numpy()

    wyniki = {}
    for nazwa in CECHY:
        wyniki[nazwa] = np.full(len(dane), np.nan)
    wyniki["liczba_transakcji_2km_24m"][:] = 0


    print("Sąsiedztwo, część 1: mediana ceny w obrębie", flush=True)
    for wiersze_obrebu in dane.groupby("teryt_obreb").indices.values():
        zrodla = wiersze_obrebu[trening[wiersze_obrebu]]
        zrodla = zrodla[np.argsort(daty[zrodla], kind="stable")]
        if len(zrodla) == 0:
            continue

        for i in wiersze_obrebu:
            ile_wczesniejszych = np.searchsorted(daty[zrodla], daty[i], side="left")
            wczesniejsze = zrodla[:ile_wczesniejszych]
            wczesniejsze = wczesniejsze[dzialki[wczesniejsze] != dzialki[i]]
            if len(wczesniejsze) > 0:
                wyniki["mediana_cena_m2_obreb"][i] = np.median(ceny[wczesniejsze])

    print("Sąsiedztwo, część 2: mediana ceny w gminie", flush=True)
    for wiersze_gminy in dane.groupby("teryt_gmina").indices.values():
        zrodla = wiersze_gminy[trening[wiersze_gminy]]
        zrodla = zrodla[np.argsort(daty[zrodla], kind="stable")]
        if len(zrodla) == 0:
            continue

        for i in wiersze_gminy:
            ile_wczesniejszych = np.searchsorted(daty[zrodla], daty[i], side="left")
            wczesniejsze = zrodla[:ile_wczesniejszych]
            wczesniejsze = wczesniejsze[dzialki[wczesniejsze] != dzialki[i]]
            if len(wczesniejsze) == 0:
                continue

            wyniki["mediana_cena_m2_gmina"][i] = np.median(ceny[wczesniejsze])

    print("Sąsiedztwo, część 3: sprzedaże w promieniu 2 i 5 km", flush=True)
    sprzedaze_treningowe = np.flatnonzero(trening)
    drzewo = cKDTree(xy[sprzedaze_treningowe])
    pierwsza_data = daty[sprzedaze_treningowe].min()
    start = time.monotonic()

    for i in range(len(dane)):
        if i % 50000 == 0:
            print(f"  {i:,}/{len(dane):,}, {time.monotonic() - start:.0f} s", flush=True)

        w_promieniu_5km = sprzedaze_treningowe[np.asarray(drzewo.query_ball_point(xy[i], r=5000), dtype=int)]
        sasiedzi = w_promieniu_5km[(daty[w_promieniu_5km] < daty[i]) & (dzialki[w_promieniu_5km] != dzialki[i])]
        odleglosci = np.linalg.norm(xy[sasiedzi] - xy[i], axis=1)

        if len(sasiedzi) > 0:
            wyniki["odl_najblizsza_transakcja_m"][i] = odleglosci.min()
        elif daty[i] > pierwsza_data:
            ile = min(32, len(sprzedaze_treningowe))
            while True:
                dystanse, pozycje = drzewo.query(xy[i], k=ile)
                kandydaci = sprzedaze_treningowe[np.atleast_1d(pozycje)]
                pasuja = (daty[kandydaci] < daty[i]) & (dzialki[kandydaci] != dzialki[i])
                if pasuja.any():
                    wyniki["odl_najblizsza_transakcja_m"][i] = np.atleast_1d(dystanse)[pasuja].min()
                    break
                if ile == len(sprzedaze_treningowe):
                    break
                ile = min(ile * 2, len(sprzedaze_treningowe))

        z_ostatnich_24_mies = daty[sasiedzi] >= dwa_lata_wczesniej[i]
        sasiedzi = sasiedzi[z_ostatnich_24_mies]
        odleglosci = odleglosci[z_ostatnich_24_mies]
        if len(sasiedzi) == 0:
            continue

        wyniki["mediana_cena_m2_5km_24m"][i] = np.median(ceny[sasiedzi])

        w_promieniu_2km = sasiedzi[odleglosci <= 2000]
        wyniki["liczba_transakcji_2km_24m"][i] = len(w_promieniu_2km)
        if len(w_promieniu_2km) == 0:
            continue

        wyniki["mediana_cena_m2_2km_24m"][i] = np.median(ceny[w_promieniu_2km])

        if uzytki[i] != "":
            ten_sam_uzytek = w_promieniu_2km[uzytki[w_promieniu_2km] == uzytki[i]]
            if len(ten_sam_uzytek) > 0:
                wyniki["mediana_cena_m2_2km_ten_sam_uzytek"][i] = np.median(ceny[ten_sam_uzytek])

    for nazwa in CECHY:
        dane[nazwa] = wyniki[nazwa]
    return dane
