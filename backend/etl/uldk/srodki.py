from pathlib import Path

import numpy as np
import pandas as pd

import config

NAZWA_ZAPISU = "uldk_srodki.parquet"


def wczytaj_zapis(sciezka=None):
    sciezka = (
        Path(sciezka)
        if sciezka is not None
        else Path(config.SCIEZKA_POSREDNIE) / NAZWA_ZAPISU
    )
    if not sciezka.exists():
        return pd.DataFrame(columns=["dzi_id_dzialki", "x_2180", "y_2180"])
    return pd.read_parquet(sciezka)


def dodaj_srodki_uldk(dane, zapis=None):
    if zapis is None:
        zapis = wczytaj_zapis()
    for kolumna in ["x_2180", "y_2180"]:
        if kolumna not in dane:
            dane[kolumna] = np.nan
    if "zrodlo_srodka" not in dane:
        dane["zrodlo_srodka"] = "brak"
    if zapis.empty:
        return dane
    dobre = np.isfinite(zapis["x_2180"]) & np.isfinite(zapis["y_2180"])
    po_id = (
        zapis.loc[dobre]
        .drop_duplicates("dzi_id_dzialki", keep="last")
        .set_index("dzi_id_dzialki")
    )
    brak = ~np.isfinite(dane["x_2180"]) | ~np.isfinite(dane["y_2180"])
    x = dane["dzi_id_dzialki"].map(po_id["x_2180"])
    y = dane["dzi_id_dzialki"].map(po_id["y_2180"])
    uzupelnij = brak & np.isfinite(x) & np.isfinite(y)
    dane.loc[uzupelnij, "x_2180"] = x[uzupelnij]
    dane.loc[uzupelnij, "y_2180"] = y[uzupelnij]
    dane.loc[uzupelnij, "zrodlo_srodka"] = "uldk_cache_srodki"
    return dane
