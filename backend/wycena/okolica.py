from psycopg import sql

from etl.wczytanie_i_czyszczenie_cech.pozostale import PRZEZNACZENIA

# Cechy, dla których ma sens pozycja na tle gminy. Bez flag 0/1, czasu i współrzędnych.
BEZ_PERCENTYLA = {"rok", "miesiace_od_2015", "x_2180", "y_2180", "ma_wpis_przeznaczenia"}


def transakcje_wokol(baza, parametry):
    # Sprzedaże do mapy: te same, z których liczy się sąsiedztwo cenowe w 5 km.
    wiersze = baza.execute(
        """
        SELECT ST_X(ST_Transform(srodek, 4326)), ST_Y(ST_Transform(srodek, 4326)),
               cena_m2, dok_data::date, powierzchnia_m2, dzi_sposob_uzyt
        FROM dane.transakcje
        WHERE ST_DWithin(srodek, ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180), 5000)
          AND dok_data < %(dzien)s
          AND dok_data >= %(dzien)s - interval '24 months'
          AND dzi_id_dzialki IS DISTINCT FROM %(dzialka)s
        ORDER BY srodek <-> ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180)
        LIMIT 2000
        """,
        parametry,
    ).fetchall()

    transakcje = []
    for dlugosc, szerokosc, cena, dzien, powierzchnia, rodzaj in wiersze:
        transakcje.append({
            "punkt": [dlugosc, szerokosc],
            "cenaM2": cena,
            "data": dzien.isoformat(),
            "powierzchnia": powierzchnia,
            "rodzaj": rodzaj,
        })
    return transakcje


def poprzednie_sprzedaze(baza, parametry):
    if parametry["dzialka"] is None:
        return []
    wiersze = baza.execute(
        """
        SELECT dok_data::date, cena_m2, tran_cena_brutto
        FROM dane.transakcje
        WHERE dzi_id_dzialki = %(dzialka)s AND dok_data < %(dzien)s
        ORDER BY dok_data
        """,
        parametry,
    ).fetchall()
    return [{"data": dzien.isoformat(), "cenaM2": cena, "cena": calosc} for dzien, cena, calosc in wiersze]


def historia_gminy(baza, parametry):
    miesiace = baza.execute(
        """
        SELECT to_char(date_trunc('month', dok_data), 'YYYY-MM'),
               percentile_cont(0.5) WITHIN GROUP (ORDER BY cena_m2),
               count(*)
        FROM dane.transakcje
        WHERE teryt_gmina = %(gmina)s
          AND dok_data < %(dzien)s
          AND dok_data >= date_trunc('month', %(dzien)s - interval '23 months')
        GROUP BY 1
        ORDER BY 1
        """,
        parametry,
    ).fetchall()

    mediana_teraz, wszystkie = baza.execute(
        """
        SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY cena_m2) FILTER (WHERE dok_data >= %(dzien)s - interval '12 months'),
               count(*)
        FROM dane.transakcje
        WHERE teryt_gmina = %(gmina)s AND dok_data < %(dzien)s
        """,
        parametry,
    ).fetchone()

    punkty = [{"miesiac": miesiac, "mediana": mediana, "liczba": liczba} for miesiac, mediana, liczba in miesiace]
    return {"punkty": punkty, "medianaTeraz": mediana_teraz, "transakcje": wszystkie}


def percentyle(baza, cechy, liczbowe):
    # Jaka część sprzedanych działek w gminie ma mniejszą wartość cechy.
    # W małej gminie porównujemy z całym powiatem.
    kody = []
    for kod in liczbowe:
        if kod in BEZ_PERCENTYLA or kod.startswith("przezn_") or kod.startswith("czy_"):
            continue
        if cechy.get(kod) is not None:
            kody.append(kod)

    obszar = "gmina"
    liczba = baza.execute("SELECT count(*) FROM dane.transakcje WHERE teryt_gmina = %s", (cechy["teryt_gmina"],)).fetchone()[0]
    if liczba < 30:
        obszar = "powiat"

    udzialy = []
    for kod in kody:
        udzialy.append(
            sql.SQL("avg(({kolumna} < {wartosc})::int) FILTER (WHERE {kolumna} IS NOT NULL)").format(
                kolumna=sql.Identifier(kod), wartosc=sql.Literal(float(cechy[kod]))
            )
        )
    zapytanie = sql.SQL("SELECT {} FROM dane.transakcje WHERE {} = %s").format(
        sql.SQL(", ").join(udzialy), sql.Identifier("teryt_" + obszar)
    )
    wiersz = baza.execute(zapytanie, (cechy["teryt_" + obszar],)).fetchone()

    wynik = {}
    for kod, udzial in zip(kody, wiersz):
        wynik[kod] = None if udzial is None else round(float(udzial) * 100)
    return {"obszar": obszar, "percentyle": wynik}


def podpowiedz(baza, obreb):
    # Najczęstsze przeznaczenie i rodzaj gruntu wśród sprzedaży w obrębie, a gdy ich brak — w gminie.
    gmina = obreb[:6] + obreb[7]
    for kolumna, teryt in [("teryt_obreb", obreb), ("teryt_gmina", gmina)]:
        warunek = sql.SQL("{} = %s").format(sql.Identifier(kolumna))

        wpisy = baza.execute(
            sql.SQL(
                """
                SELECT trim(wpis), count(*)
                FROM dane.transakcje, unnest(string_to_array(dzi_przezn_wmpzp, ';')) AS wpis
                WHERE {} AND trim(wpis) <> ''
                GROUP BY 1
                ORDER BY 2 DESC
                """
            ).format(warunek),
            (teryt,),
        ).fetchall()
        z_wpisem = baza.execute(
            sql.SQL("SELECT count(*) FROM dane.transakcje WHERE {} AND coalesce(trim(dzi_przezn_wmpzp), '') <> ''").format(warunek),
            (teryt,),
        ).fetchone()[0]
        rodzaje = baza.execute(
            sql.SQL(
                """
                SELECT dzi_sposob_uzyt, count(*), sum(count(*)) OVER ()
                FROM dane.transakcje
                WHERE {} AND dzi_sposob_uzyt IS NOT NULL
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 1
                """
            ).format(warunek),
            (teryt,),
        ).fetchone()

        znane = [(kod, liczba) for kod, liczba in wpisy if kod in PRZEZNACZENIA]
        if not znane:
            continue

        kod, liczba = znane[0]
        wynik = {
            "obszar": "obreb" if kolumna == "teryt_obreb" else "gmina",
            "przeznaczenie": kod,
            "udzial": round(liczba / z_wpisem * 100),
            "liczbaSprzedazy": z_wpisem,
            "rodzajGruntu": None,
        }
        if rodzaje:
            wynik["rodzajGruntu"] = {"kod": rodzaje[0], "udzial": round(rodzaje[1] / rodzaje[2] * 100)}
        return wynik

    return None
