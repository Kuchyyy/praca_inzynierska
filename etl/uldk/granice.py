import sqlite3
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
from shapely import wkt
from shapely.errors import GEOSException

import config

ADRES = "https://uldk.gugik.gov.pl/"


def otworz_cache(sciezka):
    Path(sciezka).parent.mkdir(parents=True, exist_ok=True)
    baza = sqlite3.connect(sciezka)
    baza.execute("""CREATE TABLE IF NOT EXISTS granice (
        id TEXT PRIMARY KEY, geometry BLOB, pobrano_utc TEXT, status TEXT
    )""")
    baza.commit()
    return baza


def granica_z_odpowiedzi(tekst, identyfikator):
    linie = [linia.strip() for linia in tekst.splitlines() if linia.strip()]
    if linie and linie[0].startswith("-"):
        return None, "brak_wyniku"
    if len(linie) != 2 or linie[0] != "0":
        return None, "bledna_odpowiedz"
    pola = linie[1].split("|")
    if len(pola) != 2 or pola[0].strip() != identyfikator:
        return None, "bledny_id_odpowiedzi"
    tekst_granicy = pola[1].strip()
    if tekst_granicy.upper().startswith("SRID="):
        srid, tekst_granicy = tekst_granicy.split(";", 1)
        if srid.upper() != "SRID=2180":
            return None, "bledny_crs"
    try:
        ksztalt = wkt.loads(tekst_granicy)
        if (
            ksztalt.geom_type not in {"Polygon", "MultiPolygon"}
            or ksztalt.is_empty
            or not ksztalt.is_valid
            or not np.isfinite(ksztalt.area)
            or ksztalt.area <= 0
        ):
            return None, "bledna_geometria"
    except (ValueError, GEOSException):
        return None, "bledna_geometria"
    return ksztalt.wkb, "ok"


def pobierz_granice(identyfikator):
    zapytanie = urlencode(
        {
            "request": "GetParcelById",
            "id": identyfikator,
            "result": "id,geom_wkt",
            "srid": 2180,
        }
    )
    try:
        with urlopen(ADRES + "?" + zapytanie, timeout=30) as odpowiedz:
            tekst = odpowiedz.read().decode("utf-8")
        return granica_z_odpowiedzi(tekst, identyfikator)
    except (URLError, TimeoutError, OSError, UnicodeError):
        return None, "blad_sieci"


def znajdz_granice(identyfikatory, baza, pobieranie):
    if baza is None:
        return {}
    identyfikatory = list(dict.fromkeys(identyfikatory))
    zapis = {}
    for start in range(0, len(identyfikatory), 900):
        czesc = identyfikatory[start : start + 900]
        znaki = ",".join("?" for _ in czesc)
        for identyfikator, geometria, kiedy, status in baza.execute(
            f"SELECT id, geometry, pobrano_utc, status FROM granice WHERE id IN ({znaki})",
            czesc,
        ):
            zapis[identyfikator] = (geometria, kiedy, status)
    for identyfikator in identyfikatory:
        if pobieranie is None or pobieranie["pozostalo"] <= 0:
            break
        poprzedni = zapis.get(identyfikator)
        if poprzedni:
            if poprzedni[2] == "ok":
                continue
            if datetime.now(timezone.utc) - datetime.fromisoformat(
                poprzedni[1]
            ) < timedelta(days=1):
                continue
        plik_cache = baza.execute("PRAGMA database_list").fetchone()[2]
        if (
            plik_cache
            and shutil.disk_usage(Path(plik_cache).parent).free
            < config.ZAPAS_DYSKU_GIB * 1024**3 + 256 * 1024**2
        ):
            raise RuntimeError("Za malo miejsca na kolejne granice ULDK")
        geometria, status = pobierz_granice(identyfikator)
        kiedy = datetime.now(timezone.utc).isoformat()
        with baza:
            baza.execute(
                "INSERT OR REPLACE INTO granice VALUES (?, ?, ?, ?)",
                (identyfikator, geometria, kiedy, status),
            )
        zapis[identyfikator] = (geometria, kiedy, status)
        pobieranie["pozostalo"] -= 1
        pobieranie["zapytania"] += 1
        pobieranie["pobrane"] += int(status == "ok")
        print(
            f"  ULDK {pobieranie['zapytania']}: {identyfikator}, {status}", flush=True
        )
        # Po bledzie tez dajemy usludze chwile oddechu.
        time.sleep(0.5)
    return {
        identyfikator: (g, kiedy)
        for identyfikator, (g, kiedy, status) in zapis.items()
        if status == "ok"
    }
