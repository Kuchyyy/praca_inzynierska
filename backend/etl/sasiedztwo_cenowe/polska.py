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
    "trend_cen_gmina_12m",
    "odl_najblizsza_transakcja_m",
]


def dodaj_sasiedztwo(dane, test_od, pokaz_postep=None):
    dane = dane.reset_index(drop=True).copy()
    daty = dane["dok_data"].dt.normalize().to_numpy()
    ceny = dane["cena_m2"].to_numpy()
    dzialki = dane["dzi_id_dzialki"].to_numpy()
    uzytki = dane["dzi_sposob_uzyt"].fillna("").to_numpy()
    xy = dane[["x_2180", "y_2180"]].to_numpy()
    trening = daty < np.datetime64(test_od)
    dane["zbior"] = np.where(trening, "trening", "test")

    if not trening.any():
        raise ValueError("Brak transakcji treningowych przed data podzialu")
    if not np.isfinite(xy).all() or not np.isfinite(ceny).all() or (ceny <= 0).any():
        raise ValueError("Sasiedztwo wymaga poprawnych wspolrzednych i cen")

    dol24 = (dane["dok_data"].dt.normalize() - pd.DateOffset(months=24)).to_numpy()
    dol12 = (dane["dok_data"].dt.normalize() - pd.DateOffset(months=12)).to_numpy()
    wyniki = {nazwa: np.full(len(dane), np.nan) for nazwa in CECHY}
    wyniki["liczba_transakcji_2km_24m"][:] = 0

    # Jedna gmina lub obreb naraz; test nigdy nie jest zrodlem cen.
    for kolumna, nazwa in [
        ("teryt_gmina", "mediana_cena_m2_gmina"),
        ("teryt_obreb", "mediana_cena_m2_obreb"),
    ]:
        print(f"Sasiedztwo: {kolumna}", flush=True)
        for _, indeksy in dane.groupby(kolumna).indices.items():
            zrodlo = indeksy[trening[indeksy]]
            zrodlo = zrodlo[np.argsort(daty[zrodlo], kind="stable")]
            if not len(zrodlo):
                continue
            for i in indeksy:
                koniec = np.searchsorted(daty[zrodlo], daty[i], side="left")
                wczesniejsze = zrodlo[:koniec]
                # Wczesniejsza sprzedaz tej samej dzialki nie jest sasiadem.
                wczesniejsze = wczesniejsze[dzialki[wczesniejsze] != dzialki[i]]
                if not len(wczesniejsze):
                    continue
                wyniki[nazwa][i] = np.median(ceny[wczesniejsze])
                if kolumna == "teryt_gmina":
                    ostatni_rok = wczesniejsze[daty[wczesniejsze] >= dol12[i]]
                    poprzedni_rok = wczesniejsze[
                        (daty[wczesniejsze] >= dol24[i])
                        & (daty[wczesniejsze] < dol12[i])
                    ]
                    if len(ostatni_rok) and len(poprzedni_rok):
                        wyniki["trend_cen_gmina_12m"][i] = (
                            np.median(ceny[ostatni_rok])
                            / np.median(ceny[poprzedni_rok])
                            - 1
                        )

    referencje = np.flatnonzero(trening)
    drzewo = cKDTree(xy[referencje])
    pierwsza_data = daty[referencje].min()
    start = time.monotonic()

    for i in range(len(dane)):
        if i % 10000 == 0:
            czas = time.monotonic() - start
            eta = czas / i * (len(dane) - i) if i else None
            print(
                (
                    f"Sasiedztwo przestrzenne: {i:,}/{len(dane):,}, pozostalo ok. {eta / 60:.1f} min"
                    if eta
                    else f"Sasiedztwo przestrzenne: {i:,}/{len(dane):,}"
                ),
                flush=True,
            )
            if pokaz_postep is not None:
                pokaz_postep(i, len(dane), eta)

        # Nie budujemy list sasiedztwa dla calej Polski jednoczesnie.
        indeksy = referencje[
            np.asarray(drzewo.query_ball_point(xy[i], r=5000), dtype=int)
        ]
        indeksy = indeksy[(daty[indeksy] < daty[i]) & (dzialki[indeksy] != dzialki[i])]
        odleglosci = np.linalg.norm(xy[indeksy] - xy[i], axis=1)

        if len(indeksy):
            wyniki["odl_najblizsza_transakcja_m"][i] = odleglosci.min()
        elif daty[i] > pierwsza_data:
            # Najblizsza wczesniejsza transakcja moze lezec dalej niz 5 km.
            ile = min(32, len(referencje))
            while ile:
                dystanse, pozycje = drzewo.query(xy[i], k=ile)
                kandydaci = referencje[np.atleast_1d(pozycje)]
                pasuja = (daty[kandydaci] < daty[i]) & (
                    dzialki[kandydaci] != dzialki[i]
                )
                if pasuja.any():
                    wyniki["odl_najblizsza_transakcja_m"][i] = np.atleast_1d(dystanse)[
                        pasuja
                    ].min()
                    break
                if ile == len(referencje):
                    break
                ile = min(ile * 2, len(referencje))

        w_oknie = daty[indeksy] >= dol24[i]
        indeksy = indeksy[w_oknie]
        odleglosci = odleglosci[w_oknie]
        if not len(indeksy):
            continue

        wyniki["mediana_cena_m2_5km_24m"][i] = np.median(ceny[indeksy])
        blisko = indeksy[odleglosci <= 2000]
        wyniki["liczba_transakcji_2km_24m"][i] = len(blisko)
        if len(blisko):
            wyniki["mediana_cena_m2_2km_24m"][i] = np.median(ceny[blisko])
            ten_sam = blisko[uzytki[blisko] == uzytki[i]] if uzytki[i] else []
            if len(ten_sam):
                wyniki["mediana_cena_m2_2km_ten_sam_uzytek"][i] = np.median(
                    ceny[ten_sam]
                )

    for nazwa in CECHY:
        dane[nazwa] = wyniki[nazwa]
    return dane
