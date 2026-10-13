from pathlib import Path

import psycopg

import config


def ustawienia_bazy():
    ustawienia = {}
    plik = Path(config.POSTGRES_ENV)
    if plik.exists():
        for wiersz in plik.read_text().splitlines():
            if wiersz.strip() and not wiersz.lstrip().startswith("#"):
                nazwa, wartosc = wiersz.split("=", 1)
                ustawienia[nazwa.strip()] = wartosc.strip()
    return ustawienia


def polacz(administrator=False):
    ustawienia = ustawienia_bazy()
    uzytkownik = "dzialki_app"
    haslo = ustawienia.get("APP_DB_PASSWORD")
    if administrator:
        uzytkownik = ustawienia.get("POSTGRES_USER", "postgres")
        haslo = ustawienia.get("POSTGRES_PASSWORD")

    return psycopg.connect(
        host=config.POSTGRES_HOST,
        port=ustawienia.get("POSTGRES_PORT", "5432"),
        dbname=ustawienia.get("POSTGRES_DB", "dzialki"),
        user=uzytkownik,
        password=haslo or None,
        autocommit=True,
    )
