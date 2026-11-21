import shutil
import zipfile
from http.client import HTTPException
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pyogrio

import config
from etl.etap3_granice.granice import brakujace_dzialki, otworz_cache
from etl.etap2_4_czyszczenie.geometria import wczytaj_ksztalt

ADRES = "https://opendata.geoportal.gov.pl/InneDane/latest_exports/eziudp_wfs/GPKG/"


def pobierz_paczke(powiat, katalog):
    plik_zip = katalog / f"{powiat}.gpkg.zip"
    with urlopen(ADRES + plik_zip.name, timeout=90) as odpowiedz, plik_zip.open("wb") as zapis:
        shutil.copyfileobj(odpowiedz, zapis)

    gpkg = katalog / f"{powiat}.gpkg"
    with zipfile.ZipFile(plik_zip) as archiwum:
        nazwa = [n for n in archiwum.namelist() if n.lower().endswith(".gpkg")][0]
        with archiwum.open(nazwa) as dane, gpkg.open("wb") as zapis:
            shutil.copyfileobj(dane, zapis)

    plik_zip.unlink()
    return gpkg


def wybierz_granice(gpkg, szukane):
    znalezione = {}
    sprzeczne = set()

    with pyogrio.open_arrow(gpkg, layer="dzialki", columns=["id_dzialki"], batch_size=10000, use_pyarrow=True) as (opis, partie):
        for partia in partie:
            for wiersz in partia.to_pylist():
                identyfikator = wiersz["id_dzialki"]
                if identyfikator not in szukane or identyfikator in sprzeczne:
                    continue

                ksztalt = wczytaj_ksztalt(wiersz[opis["geometry_name"]])
                if ksztalt is None:
                    continue

                if identyfikator in znalezione:
                    if not ksztalt.equals(wczytaj_ksztalt(znalezione[identyfikator])):
                        sprzeczne.add(identyfikator)
                        del znalezione[identyfikator]
                    continue

                znalezione[identyfikator] = ksztalt.wkb

    return znalezione


def uzupelnij_egib():
    baza = otworz_cache(config.SCIEZKA_ULDK_GRANICE)
    katalog = Path(config.SCIEZKA_PACZKI_EGIB)
    katalog.mkdir(parents=True, exist_ok=True)

    z_uldk = {r[0] for r in baza.execute("SELECT id FROM granice WHERE status = 'ok'")}
    gotowe_powiaty = {r[0] for r in baza.execute("SELECT powiat FROM paczki_egib")}

    powiaty = {}
    for identyfikator in brakujace_dzialki(config.SCIEZKA_OCZYSZCZONE):
        if identyfikator not in z_uldk:
            powiaty.setdefault(identyfikator[:4], set()).add(identyfikator)

    for numer, powiat in enumerate(sorted(powiaty), 1):
        if powiat in gotowe_powiaty:
            continue

        try:
            gpkg = pobierz_paczke(powiat, katalog)
        except (URLError, HTTPException, TimeoutError, ConnectionError) as blad:
            print(f"Powiat {powiat}: nie pobrano paczki ({blad}), spróbuję przy następnym uruchomieniu")
            continue

        znalezione = wybierz_granice(gpkg, powiaty[powiat])
        gpkg.unlink()

        with baza:
            baza.executemany("INSERT OR REPLACE INTO granice_egib (id, geometry) VALUES (?, ?)", znalezione.items())
            baza.execute("INSERT OR REPLACE INTO paczki_egib (powiat, znalezione) VALUES (?, ?)", (powiat, len(znalezione)))
        print(f"Powiat {powiat} ({numer}/{len(powiaty)}): {len(znalezione):,} z {len(powiaty[powiat]):,} granic", flush=True)

    baza.close()
