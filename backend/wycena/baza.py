from pathlib import Path

import psycopg

import config


def ustawienia_bazy():
    # Plik .env jest opcjonalny. Bez niego łączymy się z domyślną bazą bez hasła.
    ustawienia = {}
    plik = Path(config.POSTGRES_ENV)
    if plik.exists():
        for wiersz in plik.read_text().splitlines():
            if wiersz.strip() and not wiersz.lstrip().startswith("#"):
                nazwa, wartosc = wiersz.split("=", 1)
                ustawienia[nazwa.strip()] = wartosc.strip()
    return ustawienia


def polacz():
    # Panel korzysta z konta aplikacji, nie z administratora bazy.
    ustawienia = ustawienia_bazy()
    return psycopg.connect(
        host=config.POSTGRES_HOST,
        port=ustawienia.get("POSTGRES_PORT", "5432"),
        dbname=ustawienia.get("POSTGRES_DB", "dzialki"),
        user="dzialki_app",
        password=ustawienia.get("APP_DB_PASSWORD") or None,
        autocommit=True,
        application_name="wycena",
    )
