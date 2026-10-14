import numpy as np
import pandas as pd
from shapely import wkb
from shapely.errors import GEOSException

import config
from etl.etap3_granice.granice import granice_z_cache


def wczytaj_ksztalt(dane_binarne):
    if dane_binarne is None:
        return None

    try:
        ksztalt = wkb.loads(bytes(dane_binarne))
    except (ValueError, TypeError, GEOSException):
        return None

    if ksztalt.geom_type not in ["Polygon", "MultiPolygon"]:
        return None
    if ksztalt.is_empty or not ksztalt.is_valid:
        return None
    if not np.isfinite(ksztalt.area) or ksztalt.area <= 0:
        return None
    return ksztalt


def ustal_powierzchnie(pow_ewid, pole_z_granicy):
    # Powierzchnia z ewidencji musi się zgadzać z polem granicy. Czasem wpisano ją w hektarach.
    if pd.isna(pow_ewid) or not np.isfinite(pow_ewid) or pow_ewid <= 0:
        return pole_z_granicy, "pole_z_geometrii"

    stosunek = pow_ewid / pole_z_granicy
    if config.TOLERANCJA_POLA_DOL <= stosunek <= config.TOLERANCJA_POLA_GORA:
        return pow_ewid, "ewidencja_m2"

    stosunek_ha = pow_ewid * 10000 / pole_z_granicy
    if config.TOLERANCJA_POLA_DOL <= stosunek_ha <= config.TOLERANCJA_POLA_GORA:
        return pow_ewid * 10000, "ewidencja_ha"

    return np.nan, "rozbieznosc_powierzchni"


def dodaj_geometrie(df, baza_granic):
    df = df.copy()

    bez_granicy_w_rcn = []
    for identyfikator, geometria in zip(df["dzi_id_dzialki"], df["geometry"]):
        if wczytaj_ksztalt(geometria) is None:
            bez_granicy_w_rcn.append(identyfikator)
    granice_pobrane = granice_z_cache(bez_granicy_w_rcn, baza_granic)

    geometrie = []
    zrodla_geometrii = []
    pola = []
    obwody = []
    x = []
    y = []
    powierzchnie = []
    zrodla_powierzchni = []

    for identyfikator, geometria, pow_ewid in zip(df["dzi_id_dzialki"], df["geometry"], df["dzi_pow_ewid"]):
        ksztalt = wczytaj_ksztalt(geometria)
        zrodlo = "rcn"

        if ksztalt is None:
            zrodlo = "brak"
            if identyfikator in granice_pobrane:
                geometria_pobrana, zrodlo_pobranej = granice_pobrane[identyfikator]
                ksztalt = wczytaj_ksztalt(geometria_pobrana)
                if ksztalt is not None:
                    zrodlo = zrodlo_pobranej

        zrodla_geometrii.append(zrodlo)

        if ksztalt is None:
            geometrie.append(None)
            pola.append(np.nan)
            obwody.append(np.nan)
            x.append(np.nan)
            y.append(np.nan)
            powierzchnie.append(np.nan)
            zrodla_powierzchni.append("brak_geometrii_do_weryfikacji")
            continue

        srodek = ksztalt.centroid
        powierzchnia, zrodlo_powierzchni = ustal_powierzchnie(pow_ewid, ksztalt.area)

        geometrie.append(ksztalt.wkb)
        pola.append(ksztalt.area)
        obwody.append(ksztalt.length)
        x.append(srodek.x)
        y.append(srodek.y)
        powierzchnie.append(powierzchnia)
        zrodla_powierzchni.append(zrodlo_powierzchni)

    df["geometry"] = geometrie
    df["zrodlo_geometrii"] = zrodla_geometrii
    df["pole_geom_m2"] = pola
    df["obwod_m"] = obwody
    df["x_2180"] = x
    df["y_2180"] = y
    df["powierzchnia_m2"] = pd.Series(powierzchnie, index=df.index, dtype="float64")
    df["zrodlo_powierzchni"] = zrodla_powierzchni
    return df
