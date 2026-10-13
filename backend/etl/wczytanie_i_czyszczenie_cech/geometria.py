import numpy as np
import pandas as pd
from shapely import wkb
from shapely.errors import GEOSException

import config
from etl.uldk.granice import granice_z_cache


def wczytaj_ksztalt(dane_binarne):
    if dane_binarne is None:
        return None
    try:
        ksztalt = wkb.loads(bytes(dane_binarne))
    except (ValueError, TypeError, GEOSException):
        return None
    if ksztalt.geom_type not in {"Polygon", "MultiPolygon"}:
        return None
    if ksztalt.is_empty or not ksztalt.is_valid or not np.isfinite(ksztalt.area) or ksztalt.area <= 0:
        return None
    return ksztalt


def ustal_powierzchnie(pow_ewid, pole_z_geometrii):
    if not np.isfinite(pole_z_geometrii) or pole_z_geometrii <= 0:
        return np.nan, "brak_geometrii_do_weryfikacji"
    if pd.isna(pow_ewid) or not np.isfinite(pow_ewid) or pow_ewid <= 0:
        return pole_z_geometrii, "pole_z_geometrii"

    stosunek = pow_ewid / pole_z_geometrii
    if config.TOLERANCJA_POLA_DOL <= stosunek <= config.TOLERANCJA_POLA_GORA:
        return pow_ewid, "ewidencja_m2"
    if config.TOLERANCJA_POLA_DOL <= stosunek * 10000 <= config.TOLERANCJA_POLA_GORA:
        return pow_ewid * 10000, "ewidencja_ha"
    return np.nan, "rozbieznosc_powierzchni"


def dodaj_geometrie(df, baza_uldk):
    df = df.copy()
    ksztalty = df["geometry"].map(wczytaj_ksztalt)
    df["zrodlo_geometrii"] = ["rcn" if k is not None else "brak" for k in ksztalty]

    brak = ksztalty.map(lambda k: k is None)
    granice = granice_z_cache(df.loc[brak, "dzi_id_dzialki"].tolist(), baza_uldk)
    for indeks in df.index[brak]:
        zapis = granice.get(df.at[indeks, "dzi_id_dzialki"])
        if zapis is None:
            continue
        geometria, zrodlo = zapis
        ksztalt = wczytaj_ksztalt(geometria)
        if ksztalt is not None:
            ksztalty.at[indeks] = ksztalt
            df.at[indeks, "zrodlo_geometrii"] = zrodlo

    df["geometry"] = [k.wkb if k is not None else None for k in ksztalty]
    df["pole_geom_m2"] = [k.area if k is not None else np.nan for k in ksztalty]
    df["obwod_m"] = [k.length if k is not None else np.nan for k in ksztalty]
    srodki = [k.centroid if k is not None else None for k in ksztalty]
    df["x_2180"] = [s.x if s is not None else np.nan for s in srodki]
    df["y_2180"] = [s.y if s is not None else np.nan for s in srodki]

    powierzchnie = [ustal_powierzchnie(p, g) for p, g in zip(df["dzi_pow_ewid"], df["pole_geom_m2"])]
    df["powierzchnia_m2"] = pd.Series([p[0] for p in powierzchnie], index=df.index, dtype="float64")
    df["zrodlo_powierzchni"] = pd.Series([p[1] for p in powierzchnie], index=df.index, dtype="str")
    return df
