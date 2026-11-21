import sqlite3
from http.client import HTTPException
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
from shapely import wkt
from shapely.errors import GEOSException

ADRES = "https://uldk.gugik.gov.pl/"


def otworz_cache(sciezka):
    Path(sciezka).parent.mkdir(parents=True, exist_ok=True)
    baza = sqlite3.connect(sciezka)
    baza.execute("CREATE TABLE IF NOT EXISTS granice (id TEXT PRIMARY KEY, geometry BLOB, pobrano_utc TEXT, status TEXT)")
    baza.execute("CREATE TABLE IF NOT EXISTS granice_egib (id TEXT PRIMARY KEY, geometry BLOB)")
    baza.execute("CREATE TABLE IF NOT EXISTS paczki_egib (powiat TEXT PRIMARY KEY, znalezione INTEGER)")
    baza.commit()
    return baza


def brakujace_dzialki(sciezka):
    dane = pd.read_parquet(sciezka, columns=["dzi_id_dzialki", "zrodlo_powierzchni"])
    brak = dane[dane["zrodlo_powierzchni"] == "brak_geometrii_do_weryfikacji"]
    return sorted(set(brak["dzi_id_dzialki"]))


def granice_z_cache(identyfikatory, baza):
    granice = {}
    identyfikatory = list(dict.fromkeys(identyfikatory))

    for start in range(0, len(identyfikatory), 900):
        czesc = identyfikatory[start:start + 900]
        znaki = ",".join("?" for _ in czesc)

        zapytanie = f"SELECT id, geometry FROM granice_egib WHERE id IN ({znaki})"
        for identyfikator, geometria in baza.execute(zapytanie, czesc):
            granice[identyfikator] = (geometria, "egib")

        zapytanie = f"SELECT id, geometry FROM granice WHERE status = 'ok' AND id IN ({znaki})"
        for identyfikator, geometria in baza.execute(zapytanie, czesc):
            granice[identyfikator] = (geometria, "uldk")

    return granice


def pobierz_granice(identyfikator):
    zapytanie = urlencode({"request": "GetParcelById", "id": identyfikator, "result": "id,geom_wkt", "srid": 2180})
    try:
        with urlopen(ADRES + "?" + zapytanie, timeout=30) as odpowiedz:
            linie = odpowiedz.read().decode("utf-8").strip().splitlines()
    except (HTTPException, URLError, TimeoutError, OSError, UnicodeError):
        return None, "blad_sieci"

    if len(linie) != 2 or linie[0].strip() != "0" or "|" not in linie[1]:
        return None, "brak_wyniku"

    zwrocony_id, tekst_granicy = linie[1].split("|", 1)
    if zwrocony_id.strip() != identyfikator:
        return None, "bledny_id_odpowiedzi"

    try:
        ksztalt = wkt.loads(tekst_granicy.split(";")[-1])
    except (ValueError, GEOSException):
        return None, "bledna_geometria"
    if ksztalt.geom_type not in {"Polygon", "MultiPolygon"} or not ksztalt.is_valid or ksztalt.area <= 0:
        return None, "bledna_geometria"

    return ksztalt.wkb, "ok"
