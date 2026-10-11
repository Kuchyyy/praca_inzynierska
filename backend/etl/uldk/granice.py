import sqlite3
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from http.client import HTTPException
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
    baza.execute("""CREATE TABLE IF NOT EXISTS granice_egib (
        id TEXT PRIMARY KEY, geometry BLOB, pobrano_utc TEXT,
        powiat TEXT, czas_zrodla TEXT, pole_m2 REAL
    )""")
    baza.execute("""CREATE TABLE IF NOT EXISTS paczki_egib (
        powiat TEXT PRIMARY KEY, url TEXT, sha256 TEXT, bajty INTEGER,
        pobrano_utc TEXT, znalezione INTEGER, szukane INTEGER, stan_wejscia TEXT
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
            # Jedna dzialka nie powinna sciagac setek megabajtow.
            limit = 5 * 1024 * 1024
            rozmiar = odpowiedz.headers.get("Content-Length")
            if rozmiar and rozmiar.isdigit() and int(rozmiar) > limit:
                return None, "za_duza_odpowiedz"

            dane = odpowiedz.read(limit + 1)
            if len(dane) > limit:
                return None, "za_duza_odpowiedz"
            if rozmiar and rozmiar.isdigit() and len(dane) != int(rozmiar):
                return None, "blad_sieci"

            tekst = dane.decode("utf-8")
        return granica_z_odpowiedzi(tekst, identyfikator)
    except (HTTPException, URLError, TimeoutError, OSError, UnicodeError):
        return None, "blad_sieci"


def znajdz_granice(identyfikatory, baza, pobieranie):
    if baza is None:
        return {}
    identyfikatory = list(dict.fromkeys(identyfikatory))
    zapis = {}
    zrodla = {}
    for start in range(0, len(identyfikatory), 900):
        czesc = identyfikatory[start : start + 900]
        znaki = ",".join("?" for _ in czesc)
        for identyfikator, geometria, kiedy, status in baza.execute(
            f"SELECT id, geometry, pobrano_utc, status FROM granice WHERE id IN ({znaki})",
            czesc,
        ):
            zapis[identyfikator] = (geometria, kiedy, status)
        for identyfikator, geometria, kiedy in baza.execute(
            f"SELECT id, geometry, pobrano_utc FROM granice_egib WHERE id IN ({znaki})", czesc
        ):
            if identyfikator not in zapis or zapis[identyfikator][2] != "ok":
                zapis[identyfikator] = (geometria, kiedy, "ok")
                zrodla[identyfikator] = "egib"

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
        przerwa = config.PRZERWA_ULDK if status in {"ok", "brak_wyniku"} else 2
        time.sleep(przerwa)
    return {
        identyfikator: (g, kiedy, zrodla.get(identyfikator, "uldk"))
        for identyfikator, (g, kiedy, status) in zapis.items()
        if status == "ok"
    }
