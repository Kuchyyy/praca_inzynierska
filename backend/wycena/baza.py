import psycopg

import config


def polacz(uzytkownik="dzialki_app"):
    return psycopg.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB,
        user=uzytkownik,
        autocommit=True,
    )
