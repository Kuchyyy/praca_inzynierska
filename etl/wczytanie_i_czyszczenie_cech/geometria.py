import os

import numpy as np
import pandas as pd
from shapely import wkb

import config


def wczytaj_ksztalt(dane_binarne):
    # Geometria w pliku jest w WKB.
    if dane_binarne is None:
        return None

    try:
        return wkb.loads(bytes(dane_binarne))
    except Exception:
        return None


def ustal_powierzchnie(pow_ewid, pole_z_geometrii):
    # dzi_pow_ewid bywa w hektarach albo w m2. Geometria rozstrzyga, ktora wersja pasuje.
    jako_hektary = pow_ewid * 10000
    jako_metry = pow_ewid

    if pole_z_geometrii is None or pole_z_geometrii <= 0:
        if pow_ewid < config.PROG_HEKTARY:
            return jako_hektary, "heurystyka"
        return jako_metry, "heurystyka"

    stosunek_h = jako_hektary / pole_z_geometrii
    stosunek_m = jako_metry / pole_z_geometrii

    pasuje_h = config.TOLERANCJA_POLA_DOL <= stosunek_h <= config.TOLERANCJA_POLA_GORA
    pasuje_m = config.TOLERANCJA_POLA_DOL <= stosunek_m <= config.TOLERANCJA_POLA_GORA

    if pasuje_m and not pasuje_h:
        return jako_metry, "geometria"

    if pasuje_h and not pasuje_m:
        return jako_hektary, "geometria"

    return pole_z_geometrii, "pole_z_geometrii"


def dodaj_geometrie(df):
    print()
    print("GEOMETRIA")
    print("-" * 78)
    print(f"Przetwarzanie {len(df):,} ksztaltow...")

    ksztalty = df["geometry"].map(wczytaj_ksztalt)

    # EPSG:2180 jest w metrach, wiec pole wychodzi w m2.
    pola = []
    for k in ksztalty:
        if k is not None:
            pola.append(k.area)
        else:
            pola.append(np.nan)
    df["pole_geom_m2"] = pola

    obwody = []
    for k in ksztalty:
        if k is not None:
            obwody.append(k.length)
        else:
            obwody.append(np.nan)
    df["obwod_m"] = obwody

    srodki = []
    for k in ksztalty:
        if k is not None:
            srodki.append(k.centroid)
        else:
            srodki.append(None)

    xy_x = []
    for s in srodki:
        if s is not None:
            xy_x.append(s.x)
        else:
            xy_x.append(np.nan)
    df["x_2180"] = xy_x

    xy_y = []
    for s in srodki:
        if s is not None:
            xy_y.append(s.y)
        else:
            xy_y.append(np.nan)
    df["y_2180"] = xy_y

    ma_geometrie = df["pole_geom_m2"].notna().sum()
    print(f"Udalo sie odczytac geometrie dla {ma_geometrie:,} dzialek ({100 * ma_geometrie / len(df):.1f}%)")

    print("Ustalanie, czy powierzchnia w pliku to hektary czy metry kwadratowe...")

    powierzchnie = []
    zrodla = []

    for pow_ewid, pole in zip(df["dzi_pow_ewid"], df["pole_geom_m2"]):
        if pd.isna(pole):
            pole_lub_nic = None
        else:
            pole_lub_nic = pole

        powierzchnia, zrodlo = ustal_powierzchnie(pow_ewid, pole_lub_nic)

        powierzchnie.append(powierzchnia)
        zrodla.append(zrodlo)

    df["powierzchnia_m2"] = powierzchnie
    df["zrodlo_powierzchni"] = zrodla

    for zrodlo, ile in df["zrodlo_powierzchni"].value_counts().items():
        print(f"  {zrodlo:<20} {ile:>8,}  ({100 * ile / len(df):5.1f}%)")

    sciezka = os.path.join(config.SCIEZKA_POSREDNIE, "03_z_geometria.parquet")
    df.drop(columns=["geometry"]).to_parquet(sciezka, index=False)

    return df
