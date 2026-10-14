from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree

import config
from etl.etap5_osm.warstwy import przygotuj_warstwy


def odleglosci_do_geometrii(punkty, geometrie):
    # Dla każdego środka działki odległość w metrach do najbliższego obiektu warstwy (do krawędzi, nie do środka).
    wynik = np.full(len(punkty), np.nan)
    drzewo = shapely.STRtree(geometrie)
    indeksy, dystanse = drzewo.query_nearest(punkty, all_matches=False, return_distance=True)
    wynik[indeksy[0]] = dystanse
    return wynik


def udzial_w_kole(punkty, geometrie, promien):
    # Jaka część koła wokół środka działki jest zajęta przez obszary warstwy (np. las). Od 0 do 1.
    wynik = np.zeros(len(punkty))
    drzewo = shapely.STRtree(geometrie)

    for i, punkt in enumerate(punkty):
        kolo = shapely.buffer(punkt, promien, quad_segs=16)
        dotykajace = drzewo.query(kolo, predicate="intersects")
        if len(dotykajace) == 0:
            continue

        czesci_w_kole = shapely.intersection(geometrie[dotykajace], kolo)
        zajete = shapely.union_all(czesci_w_kole).area
        wynik[i] = min(zajete / kolo.area, 1)

    return wynik


def wczytaj_warstwe(katalog, nazwa):
    warstwa = pd.read_parquet(katalog / (nazwa + ".parquet"))
    geometrie = shapely.from_wkb(warstwa["geometry"].to_numpy())
    srodki = warstwa[["x", "y"]].to_numpy()
    return geometrie, srodki


def policz_osm():
    katalog = przygotuj_warstwy()

    dane = pd.read_parquet(config.SCIEZKA_Z_GRANICAMI)
    dane = dane[dane["do_modelu"]].reset_index(drop=True)
    xy = dane[["x_2180", "y_2180"]].to_numpy()
    punkty = shapely.points(xy)
    print(f"Cechy OSM dla {len(dane):,} działek")

    print("1/7 Odległość do najbliższego budynku")
    geometrie, srodki = wczytaj_warstwe(katalog, "budynki")
    dane["odl_najblizszy_budynek_m"] = odleglosci_do_geometrii(punkty, geometrie)

    print("2/7 Liczba budynków w promieniu 1 km")
    drzewo = cKDTree(srodki)
    dane["liczba_budynkow_1000m"] = drzewo.query_ball_point(xy, r=1000, return_length=True).astype(float)
    del geometrie, srodki, drzewo

    print("3/7 Odległość do drogi")
    geometrie, srodki = wczytaj_warstwe(katalog, "drogi")
    dane["odl_droga_dowolna_m"] = odleglosci_do_geometrii(punkty, geometrie)
    del geometrie, srodki

    print("4/7 Odległość do drogi utwardzonej")
    geometrie, srodki = wczytaj_warstwe(katalog, "utwardzone")
    dane["odl_droga_utwardzona_m"] = odleglosci_do_geometrii(punkty, geometrie)
    del geometrie, srodki

    print("5/7 Udział lasu w kole 500 m")
    geometrie, srodki = wczytaj_warstwe(katalog, "las")
    dane["udzial_lasu_500m"] = udzial_w_kole(punkty, geometrie, 500)
    del geometrie, srodki

    print("6/7 Odległość do miasta powyżej 50 tys. mieszkańców")
    geometrie, srodki = wczytaj_warstwe(katalog, "miasta_50k")
    dane["odl_miasto_pow_50k_m"] = odleglosci_do_geometrii(punkty, geometrie)
    del geometrie, srodki

    print("7/7 Liczba sklepów i usług w promieniu 1 km")
    geometrie, srodki = wczytaj_warstwe(katalog, "poi")
    drzewo = cKDTree(srodki)
    dane["liczba_poi_1km"] = drzewo.query_ball_point(xy, r=1000, return_length=True).astype(float)
    del geometrie, srodki, drzewo

    Path(config.SCIEZKA_CECHY_OSM).parent.mkdir(parents=True, exist_ok=True)
    dane.to_parquet(config.SCIEZKA_CECHY_OSM, index=False)
    print(f"Zapisano: {config.SCIEZKA_CECHY_OSM}")
