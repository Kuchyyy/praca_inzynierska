import hashlib
import json
import shutil
import sqlite3
import time
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from http.client import HTTPException

import pyarrow.parquet as pq
import pyogrio
from pyproj import CRS

import config
from etl.uldk.granice import otworz_cache
from etl.wczytanie_i_czyszczenie_cech.geometria import wczytaj_ksztalt
from etl.wczytanie_i_czyszczenie_cech.wczytywanie import oczysc_plik


# Adres z oficjalnej wtyczki pobierz_dane_GUGiK, run_geoparquet_download.
ADRES = "https://opendata.geoportal.gov.pl/InneDane/latest_exports/eziudp_wfs/GPKG/"


def sprawdz_miejsce(katalog, potrzebne=0):
    wolne = shutil.disk_usage(katalog).free
    if wolne - potrzebne < config.ZAPAS_DYSKU_GIB * 1024**3 + 256 * 1024**2:
        raise RuntimeError("Za malo miejsca na paczke EGiB; zostawiam 10 GiB zapasu")


def pobierz_paczke(powiat, katalog):
    plik = katalog / f"{powiat}.gpkg.zip"
    adres = ADRES + plik.name

    # Gotowa paczka po przerwaniu moze byc wykorzystana ponownie.
    if not plik.exists():
        czesc = plik.with_suffix(".zip.part")
        for proba in range(1, 4):
            try:
                with urlopen(adres, timeout=90) as odpowiedz:
                    rozmiar = int(odpowiedz.headers["Content-Length"])
                    sprawdz_miejsce(katalog, rozmiar)

                    # Bez wersji zrodla ponawiamy cala paczke, nie doklejamy fragmentow.
                    with czesc.open("wb") as zapis:
                        while kawalek := odpowiedz.read(1024 * 1024):
                            sprawdz_miejsce(katalog, len(kawalek))
                            zapis.write(kawalek)

                if czesc.stat().st_size != rozmiar:
                    raise HTTPException("Niepelna paczka EGiB")
                break

            except (URLError, HTTPException, TimeoutError, ConnectionError) as blad:
                if isinstance(blad, HTTPError) and blad.code == 404:
                    raise
                if proba == 3:
                    raise

                print(f"Powiat {powiat}: blad sieci, ponawiam ({proba + 1}/3): {blad}", flush=True)
                time.sleep(5 * proba)

        czesc.rename(plik)

    suma = hashlib.sha256()
    with plik.open("rb") as dane:
        while kawalek := dane.read(1024 * 1024):
            suma.update(kawalek)

    gpkg = katalog / f"{powiat}.gpkg"
    with zipfile.ZipFile(plik) as archiwum:
        pliki = [p for p in archiwum.infolist() if p.filename.lower().endswith(".gpkg")]
        if len(pliki) != 1:
            raise ValueError("Oczekiwana jedna baza GeoPackage w paczce")
        sprawdz_miejsce(katalog, pliki[0].file_size)

        # Czytanie do konca sprawdza tez CRC ZIP; nazwy z archiwum nie sa sciezkami zapisu.
        with archiwum.open(pliki[0]) as dane, gpkg.open("wb") as zapis:
            while kawalek := dane.read(1024 * 1024):
                sprawdz_miejsce(katalog, len(kawalek))
                zapis.write(kawalek)

    return plik, gpkg, adres, suma.hexdigest()


def wybierz_granice(gpkg, szukane):
    znalezione = {}
    sprzeczne = set()

    with pyogrio.open_arrow(
        gpkg, layer="dzialki", columns=["id_dzialki", "czas_pozyskania"],
        batch_size=10000, use_pyarrow=True,
    ) as (opis, partie):
        if CRS.from_user_input(opis["crs"]).to_epsg() != 2180:
            raise ValueError("Paczka ma inny uklad niz EPSG:2180")

        for partia in partie:
            for wiersz in partia.to_pylist():
                identyfikator = wiersz["id_dzialki"]
                if identyfikator not in szukane or identyfikator in sprzeczne:
                    continue

                geometria = wczytaj_ksztalt(wiersz[opis["geometry_name"]])
                if geometria is None:
                    continue

                if identyfikator in znalezione:
                    poprzednia = wczytaj_ksztalt(znalezione[identyfikator][0])
                    if not geometria.equals(poprzednia):
                        sprzeczne.add(identyfikator)
                        del znalezione[identyfikator]
                    continue

                znalezione[identyfikator] = (
                    geometria.wkb, wiersz["czas_pozyskania"], geometria.area,
                )

    return znalezione, len(sprzeczne)


def uzupelnij_egib():
    wejscie = Path(config.SCIEZKA_OCZYSZCZONE)
    wynik = Path(config.SCIEZKA_PO_EGIB)
    if wynik.exists():
        raise FileExistsError(f"Wynik juz istnieje: {wynik}")

    katalog = Path(config.SCIEZKA_POSREDNIE) / "egib_paczki"
    katalog.mkdir(parents=True, exist_ok=True)
    postep = Path(config.SCIEZKA_POSREDNIE) / "egib_postep.json"
    baza = otworz_cache(config.SCIEZKA_ULDK_GRANICE)
    plik_wejscia = wejscie / "transakcje.parquet"
    stan_wejscia = f"{plik_wejscia.resolve()}:{plik_wejscia.stat().st_size}:{plik_wejscia.stat().st_mtime_ns}"
    opis = json.loads((wejscie / "podsumowanie.json").read_text())
    gotowe_uldk = {r[0] for r in baza.execute("SELECT id FROM granice WHERE status='ok'")}
    powiaty = {}

    for partia in pq.ParquetFile(plik_wejscia).iter_batches(
        columns=["dzi_id_dzialki", "zrodlo_powierzchni"]
    ):
        for wiersz in partia.to_pylist():
            identyfikator = wiersz["dzi_id_dzialki"]
            if wiersz["zrodlo_powierzchni"] != "brak_geometrii_do_weryfikacji":
                continue
            if identyfikator in gotowe_uldk:
                continue
            powiaty.setdefault(identyfikator[:4], set()).add(identyfikator)

    stan = {
        "status": "pobieranie", "powiaty": len(powiaty), "powiaty_gotowe": 0,
        "dzialki_do_sprawdzenia": sum(len(ids) for ids in powiaty.values()),
        "sprawdzone": 0, "granice_dostepne": 0, "bajty_pobrane": 0,
        "wyjscie": str(wynik), "bledy": {},
    }
    start = time.monotonic()
    czasy_paczek = []

    try:
        # Najpierw powiaty, w ktorych brakuje najwiecej dzialek.
        for powiat in sorted(powiaty, key=lambda p: len(powiaty[p]), reverse=True):
            stan["powiat"] = powiat
            poprzedni = baza.execute(
                "SELECT znalezione, bajty FROM paczki_egib WHERE powiat=? AND stan_wejscia=?",
                (powiat, stan_wejscia),
            ).fetchone()

            if poprzedni:
                ile, bajty = poprzedni
            else:
                poczatek = time.monotonic()
                print(f"Powiat {powiat}: szukam {len(powiaty[powiat]):,} dzialek", flush=True)
                stan["aktualizacja_utc"] = datetime.now(timezone.utc).isoformat()
                postep.write_text(json.dumps(stan, indent=2))

                try:
                    plik, gpkg, adres, suma = pobierz_paczke(powiat, katalog)
                    znalezione, konflikty = wybierz_granice(gpkg, powiaty[powiat])
                except (URLError, HTTPException, TimeoutError, ConnectionError) as blad:
                    stan["bledy"][powiat] = str(blad)
                    stan["aktualizacja_utc"] = datetime.now(timezone.utc).isoformat()
                    postep.write_text(json.dumps(stan, indent=2))
                    czesc = katalog / f"{powiat}.gpkg.zip.part"
                    czesc.unlink(missing_ok=True)
                    print(f"Powiat {powiat}: nie pobralem paczki, zapisany do ponowienia: {blad}", flush=True)
                    continue


                teraz = datetime.now(timezone.utc).isoformat()
                ile = len(znalezione)
                bajty = plik.stat().st_size
                sprawdz_miejsce(katalog)

                with baza:
                    for identyfikator, (geometria, czas_zrodla, pole) in znalezione.items():
                        baza.execute(
                            "INSERT OR REPLACE INTO granice_egib VALUES (?, ?, ?, ?, ?, ?)",
                            (identyfikator, geometria, teraz, powiat, czas_zrodla, pole),
                        )
                    baza.execute(
                        "INSERT OR REPLACE INTO paczki_egib VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (powiat, adres, suma, bajty, teraz, ile, len(powiaty[powiat]), stan_wejscia),
                    )

                # Usuwamy tylko nowe pliki robocze tego powiatu, po zatwierdzeniu cache.
                czasy_paczek.append(time.monotonic() - poczatek)
                gpkg.unlink()
                plik.unlink()
                print(f"Powiat {powiat}: znaleziono {ile:,}, konflikty {konflikty}, czas {time.monotonic()-poczatek:.1f} s", flush=True)

            stan["powiaty_gotowe"] += 1
            stan["sprawdzone"] += len(powiaty[powiat])
            stan["granice_dostepne"] += ile
            stan["bajty_pobrane"] += bajty
            if czasy_paczek:
                sredni_czas = sum(czasy_paczek) / len(czasy_paczek)
                pozostale = len(powiaty) - stan["powiaty_gotowe"] - len(stan["bledy"])
                stan["eta_sekundy"] = round(sredni_czas * pozostale)
            stan["czas_sekundy"] = round(time.monotonic() - start, 1)
            stan["aktualizacja_utc"] = datetime.now(timezone.utc).isoformat()
            postep.write_text(json.dumps(stan, indent=2))
            print(f"Postep {stan['powiaty_gotowe']}/{len(powiaty)} powiatow; granice: {stan['granice_dostepne']:,}", flush=True)

        stan["status"] = "przeliczanie"
        postep.write_text(json.dumps(stan, indent=2))
        oczysc_plik(
            opis["plik_zrodlowy"], wynik, date.fromisoformat(opis["data_do"]),
            opis["wielkosc_partii"], opis["wojewodztwo"], limit_uldk=0,
        )
        stan["status"] = "zakonczone_z_bledami" if stan["bledy"] else "zakonczone"

    except BaseException as blad:
        stan["status"] = "przerwane"
        stan["blad"] = str(blad)
        raise

    finally:
        baza.close()
        stan["aktualizacja_utc"] = datetime.now(timezone.utc).isoformat()
        postep.write_text(json.dumps(stan, indent=2))


if __name__ == "__main__":
    uzupelnij_egib()
