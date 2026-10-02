import numpy as np
import pandas as pd
from shapely import wkb
from shapely.errors import GEOSException

import config


def wczytaj_ksztalt(dane_binarne):
    if dane_binarne is None:
        return None
    try:
        ksztalt = wkb.loads(bytes(dane_binarne))
        if ksztalt.geom_type not in {'Polygon', 'MultiPolygon'}:
            return None
        if ksztalt.is_empty or not ksztalt.is_valid or not np.isfinite(ksztalt.area) or ksztalt.area <= 0:
            return None
        return ksztalt
    except (ValueError, TypeError, GEOSException):
        # Uszkodzone WKB nie powinno zatrzymywac calego kraju.
        return None


def ustal_powierzchnie(pow_ewid, pole_z_geometrii):
    if pole_z_geometrii is None or not np.isfinite(pole_z_geometrii) or pole_z_geometrii <= 0:
        return np.nan, 'brak_geometrii_do_weryfikacji'
    if pd.isna(pow_ewid) or not np.isfinite(pow_ewid) or pow_ewid <= 0:
        return pole_z_geometrii, 'pole_z_geometrii'
    stosunek = pow_ewid / pole_z_geometrii
    if config.TOLERANCJA_POLA_DOL <= stosunek <= config.TOLERANCJA_POLA_GORA:
        return pow_ewid, 'ewidencja_m2'
    if config.TOLERANCJA_POLA_DOL <= stosunek * 10000 <= config.TOLERANCJA_POLA_GORA:
        return pow_ewid * 10000, 'ewidencja_ha'
    return np.nan, 'rozbieznosc_powierzchni'


def dodaj_geometrie(df):
    df = df.copy()
    ksztalty = df['geometry'].map(wczytaj_ksztalt)
    df['status_geometrii'] = ['poprawna' if k is not None else 'brak_lub_bledna' for k in ksztalty]
    df['pole_geom_m2'] = [k.area if k is not None else np.nan for k in ksztalty]
    df['obwod_m'] = [k.length if k is not None else np.nan for k in ksztalty]
    srodki = [k.centroid if k is not None else None for k in ksztalty]
    df['x_2180'] = [s.x if s is not None else np.nan for s in srodki]
    df['y_2180'] = [s.y if s is not None else np.nan for s in srodki]
    powierzchnie = [ustal_powierzchnie(p, g) for p, g in zip(df['dzi_pow_ewid'], df['pole_geom_m2'])]
    df['powierzchnia_m2'] = pd.Series([p[0] for p in powierzchnie], index=df.index, dtype='float64')
    df['zrodlo_powierzchni'] = pd.Series([p[1] for p in powierzchnie], index=df.index, dtype='str')
    return df
