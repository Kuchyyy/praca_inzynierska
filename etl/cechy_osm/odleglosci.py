import os

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

import config


KOLUMNY = [
    "odl_wroclaw_m",
    "odl_miasto_pow_50k_m",
    "odl_najblizsza_miejscowosc_m",
    "odl_szkola_m",
    "odl_sklep_spozywczy_m",
]


def dodaj_odleglosci_osm(dane):
    print()
    print("ODLEGLOSCI OSM")
    print("-" * 78)

    for kolumna in KOLUMNY:
        dane[kolumna] = np.nan

    if not ma_kolumne(dane, "teryt_woj") or not ma_kolumne(dane, "x_2180"):
        print("  brak wspolrzednych, odleglosci puste")
        return dane

    for kod, indeksy in dane.groupby("teryt_woj").groups.items():
        warstwy = wczytaj_warstwy(kod)
        if warstwy is None:
            print(f"  {kod}: brak pliku OSM, odleglosci puste")
            continue

        czesc = dane.loc[indeksy]
        ma_wspolrzedne = czesc["x_2180"].notna() & czesc["y_2180"].notna()
        if not ma_wspolrzedne.any():
            print(f"  {kod}: brak wspolrzednych w wierszach")
            continue

        wiersze = czesc.index[ma_wspolrzedne]
        wspolrzedne = czesc.loc[ma_wspolrzedne, ["x_2180", "y_2180"]].to_numpy()

        dane = dodaj_odl_wroclaw(dane, wiersze, wspolrzedne, warstwy, kod)
        dane = dodaj_odl_miasto_pow_50k(dane, wiersze, wspolrzedne, warstwy)
        dane = dodaj_odl_najblizsza_miejscowosc(dane, wiersze, wspolrzedne, warstwy)
        dane = dodaj_odl_szkola(dane, wiersze, wspolrzedne, warstwy)
        dane = dodaj_odl_sklep_spozywczy(dane, wiersze, wspolrzedne, warstwy)

        print(f"  {kod}: policzono odleglosci dla {int(ma_wspolrzedne.sum()):,} dzialek")

    return dane


def dodaj_odl_wroclaw(dane, wiersze, wspolrzedne, warstwy, kod):
    if str(kod) != "02":
        return dane
    dane.loc[wiersze, "odl_wroclaw_m"] = odleglosci(wspolrzedne, punkty_warstwy(warstwy, "wroclaw"))
    return dane


def dodaj_odl_miasto_pow_50k(dane, wiersze, wspolrzedne, warstwy):
    dane.loc[wiersze, "odl_miasto_pow_50k_m"] = odleglosci(wspolrzedne, punkty_warstwy(warstwy, "miasto_50k"))
    return dane


def dodaj_odl_najblizsza_miejscowosc(dane, wiersze, wspolrzedne, warstwy):
    dane.loc[wiersze, "odl_najblizsza_miejscowosc_m"] = odleglosci(wspolrzedne, punkty_warstwy(warstwy, "miejscowosc"))
    return dane


def dodaj_odl_szkola(dane, wiersze, wspolrzedne, warstwy):
    dane.loc[wiersze, "odl_szkola_m"] = odleglosci(wspolrzedne, punkty_warstwy(warstwy, "szkola"))
    return dane


def dodaj_odl_sklep_spozywczy(dane, wiersze, wspolrzedne, warstwy):
    dane.loc[wiersze, "odl_sklep_spozywczy_m"] = odleglosci(wspolrzedne, punkty_warstwy(warstwy, "sklep"))
    return dane


def wczytaj_warstwy(kod):
    opis = config.OSM_WOJEWODZTWA.get(str(kod))
    if opis is None:
        return None

    sciezka_warstw = os.path.join(config.SCIEZKA_POSREDNIE, opis["warstwy"])
    if os.path.exists(sciezka_warstw):
        return pd.read_parquet(sciezka_warstw)

    if not os.path.exists(opis["pbf"]):
        return None

    warstwy = zbuduj_warstwy(opis["pbf"])
    os.makedirs(config.SCIEZKA_POSREDNIE, exist_ok=True)
    warstwy.to_parquet(sciezka_warstw, index=False)
    print(f"  zapisano warstwy do {sciezka_warstw}")
    return warstwy


def zbuduj_warstwy(sciezka_mapy):
    from pyrosm import OSM

    print(f"  czytam {sciezka_mapy}")
    mapa = OSM(sciezka_mapy)

    surowe_miejsca = mapa.get_data_by_custom_criteria(
        custom_filter={"place": ["city", "town", "village"]},
        filter_type="keep",
        tags_as_columns=["name", "place", "population"],
        keep_nodes=True,
        keep_ways=True,
        keep_relations=True,
    )
    miejsca = do_punktow(surowe_miejsca)

    surowe_szkoly = mapa.get_pois(custom_filter={"amenity": ["school"]})
    szkoly = do_punktow(surowe_szkoly)

    surowe_sklepy = mapa.get_pois(custom_filter={"shop": ["supermarket", "convenience"]})
    sklepy = do_punktow(surowe_sklepy)

    kawalki = [
        warstwa_wroclaw(miejsca),
        warstwa_miasto_pow_50k(miejsca),
        warstwa_miejscowosc(miejsca),
        warstwa_szkola(szkoly),
        warstwa_sklep_spozywczy(sklepy),
    ]
    kawalki = [k for k in kawalki if len(k)]
    if not kawalki:
        return pusta()
    return pd.concat(kawalki, ignore_index=True)


def warstwa_wroclaw(punkty):
    if punkty is None:
        return pusta()
    nazwa = kolumna(punkty, "name").str.casefold()
    rodzaj = kolumna(punkty, "place")
    return z_maski(punkty, ((nazwa == "wrocław") & (rodzaj == "city")).to_numpy(), "wroclaw")


def warstwa_miasto_pow_50k(punkty):
    if punkty is None:
        return pusta()
    rodzaj = kolumna(punkty, "place")
    ludnosc = pd.to_numeric(kolumna(punkty, "population"), errors="coerce")
    miasta = rodzaj.isin(["city", "town"]) & (ludnosc > 50000)
    return z_maski(punkty, miasta.to_numpy(), "miasto_50k")


def warstwa_miejscowosc(punkty):
    if punkty is None:
        return pusta()
    return z_maski(punkty, np.ones(len(punkty), dtype=bool), "miejscowosc")


def warstwa_szkola(punkty):
    if punkty is None:
        return pusta()
    return z_maski(punkty, np.ones(len(punkty), dtype=bool), "szkola")


def warstwa_sklep_spozywczy(punkty):
    if punkty is None:
        return pusta()
    return z_maski(punkty, np.ones(len(punkty), dtype=bool), "sklep")


def kolumna(punkty, nazwa):
    if not ma_kolumne(punkty, nazwa):
        return pd.Series("", index=punkty.index)
    return punkty[nazwa].fillna("").astype(str)


def ma_kolumne(ramka, nazwa):
    return nazwa in ramka.columns


def do_punktow(obiekty):
    if obiekty is None or len(obiekty) == 0 or not ma_kolumne(obiekty, "geometry"):
        return None
    obiekty = obiekty.to_crs(2180)
    geometria = obiekty["geometry"]
    obiekty = obiekty[geometria.notna() & ~geometria.is_empty].copy()
    if len(obiekty) == 0:
        return None
    srodki = obiekty["geometry"].centroid
    obiekty["x"] = srodki.x
    obiekty["y"] = srodki.y
    return obiekty


def pusta():
    return pd.DataFrame(columns=["warstwa", "x", "y"])


def z_maski(punkty, maska, nazwa):
    wybrane = punkty.loc[maska, ["x", "y"]].copy()
    wybrane["warstwa"] = nazwa
    return wybrane


def punkty_warstwy(warstwy, nazwa):
    return warstwy.loc[warstwy["warstwa"] == nazwa, ["x", "y"]].to_numpy()


def odleglosci(wspolrzedne, punkty):
    if len(punkty) == 0:
        return np.full(len(wspolrzedne), np.nan)
    drzewo = cKDTree(punkty)
    wynik, _ = drzewo.query(wspolrzedne, k=1)
    return wynik
