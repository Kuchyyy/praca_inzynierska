import os
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
from shapely import wkt

import config


NAZWA_ZAPISU = "uldk_srodki.parquet"
PRZERWA_SEKUNDY = 0.15
ADRES = "https://uldk.gugik.gov.pl/"


def dodaj_srodki_uldk(dane):
    print()
    print("SRODKI ULDK")
    print("-" * 78)

    if "x_2180" not in dane.columns:
        dane["x_2180"] = pd.NA
    if "y_2180" not in dane.columns:
        dane["y_2180"] = pd.NA

    brak = dane["x_2180"].isna() | dane["y_2180"].isna()
    if not brak.any():
        print("  wszystkie dzialki maja srodek")
        return dane

    if "dzi_id_dzialki" not in dane.columns:
        print("  brak identyfikatora dzialki")
        return dane

    identyfikatory = dane.loc[brak, "dzi_id_dzialki"].dropna().unique()
    zapis = wczytaj_zapis()
    juz_mamy = set(zapis["dzi_id_dzialki"])
    do_pobrania = [identyfikator for identyfikator in identyfikatory if identyfikator not in juz_mamy]

    print(f"  bez srodka: {len(identyfikatory):,}, do pobrania: {len(do_pobrania):,}")

    for numer, identyfikator in enumerate(do_pobrania, start=1):
        wynik = pobierz_srodek(identyfikator)
        if wynik is None:
            print(f"  {identyfikator}: brak odpowiedzi, sprobuje nastepnym razem")
            continue

        x, y = wynik
        zapis = pd.concat(
            [zapis, pd.DataFrame([{"dzi_id_dzialki": identyfikator, "x_2180": x, "y_2180": y}])],
            ignore_index=True,
        )
        zapisz(zapis)

        if numer % 100 == 0 or numer == len(do_pobrania):
            print(f"  pobrano {numer:,} z {len(do_pobrania):,}")

        time.sleep(PRZERWA_SEKUNDY)

    if len(zapis) == 0:
        return dane

    po_id = zapis.drop_duplicates("dzi_id_dzialki").set_index("dzi_id_dzialki")
    uzupelnij = dane["x_2180"].isna() | dane["y_2180"].isna()
    nowe_x = dane.loc[uzupelnij, "dzi_id_dzialki"].map(po_id["x_2180"])
    nowe_y = dane.loc[uzupelnij, "dzi_id_dzialki"].map(po_id["y_2180"])
    dane.loc[uzupelnij, "x_2180"] = nowe_x.to_numpy(dtype="float64", na_value=float("nan"))
    dane.loc[uzupelnij, "y_2180"] = nowe_y.to_numpy(dtype="float64", na_value=float("nan"))

    doszlo = int((dane.loc[brak, "x_2180"].notna() & dane.loc[brak, "y_2180"].notna()).sum())
    print(f"  dopisano srodek dla {doszlo:,} dzialek")
    return dane


def wczytaj_zapis():
    sciezka = os.path.join(config.SCIEZKA_POSREDNIE, NAZWA_ZAPISU)
    if not os.path.exists(sciezka):
        return pd.DataFrame(columns=["dzi_id_dzialki", "x_2180", "y_2180"])
    return pd.read_parquet(sciezka)


def zapisz(zapis):
    os.makedirs(config.SCIEZKA_POSREDNIE, exist_ok=True)
    sciezka = os.path.join(config.SCIEZKA_POSREDNIE, NAZWA_ZAPISU)
    zapis.to_parquet(sciezka, index=False)


def pobierz_srodek(identyfikator):
    zapytanie = urlencode({
        "request": "GetParcelById",
        "id": identyfikator,
        "result": "geom_wkt",
    })
    try:
        with urlopen(ADRES + "?" + zapytanie, timeout=30) as odpowiedz:
            tekst = odpowiedz.read().decode("utf-8")
    except (URLError, TimeoutError, OSError):
        return None

    return srodek_z_odpowiedzi(tekst)


def srodek_z_odpowiedzi(tekst):
    linie = [linia.strip() for linia in tekst.splitlines() if linia.strip()]
    if len(linie) < 2 or linie[0] != "0":
        return (None, None)

    tekst_granicy = linie[1]
    if tekst_granicy.upper().startswith("SRID="):
        tekst_granicy = tekst_granicy.split(";", 1)[1]

    try:
        srodek = wkt.loads(tekst_granicy).centroid
    except Exception:
        return (None, None)

    return (srodek.x, srodek.y)
