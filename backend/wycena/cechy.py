import json
import math
import re
from datetime import date

from psycopg import sql

from etl.etap6_cechy.cechy_dzialki import PRZEZNACZENIA

TERYT_OBREBU = re.compile(r"^(\d{2})(\d{2})(\d{2})_([1-9])\.(\d{4})$")


def cechy_formularza(dzialka):
    czesci = TERYT_OBREBU.match(dzialka["terytObrebu"])
    if czesci is None:
        raise ValueError(f"Nieznany obręb: {dzialka['terytObrebu']}")
    wojewodztwo, powiat, gmina, typ_gminy, _ = czesci.groups()

    for pole in ["rodzajGruntu", "przeznaczenie", "prawo", "sprzedajacy"]:
        if not dzialka[pole]:
            raise ValueError(f"Brak pola formularza: {pole}")

    dzien = date.fromisoformat(dzialka["dataWyceny"])
    powierzchnia = float(dzialka["powierzchnia"].replace(",", ".").replace(" ", ""))
    if powierzchnia <= 0:
        raise ValueError("Powierzchnia musi być dodatnia")

    cechy = {
        "tran_sprzedajacy": dzialka["sprzedajacy"],
        "nier_prawo": dzialka["prawo"],
        "dzi_sposob_uzyt": dzialka["rodzajGruntu"],
        "teryt_woj": wojewodztwo,
        "teryt_powiat": wojewodztwo + powiat,
        "teryt_gmina": wojewodztwo + powiat + gmina + typ_gminy,
        "rok": dzien.year,
        "miesiace_od_2015": (dzien.year - 2015) * 12 + dzien.month - 1,
        "powierzchnia_m2": powierzchnia,
        "log_powierzchnia": math.log(powierzchnia),
    }

    # W formularzu wybiera się jedno przeznaczenie: ta kolumna dostaje 1, pozostałe 0.
    for kategoria in PRZEZNACZENIA:
        if dzialka["przeznaczenie"] == kategoria:
            cechy["przezn_" + kategoria] = 1
        else:
            cechy["przezn_" + kategoria] = 0
    cechy["przezn_brak_danych"] = 0
    cechy["ma_wpis_przeznaczenia"] = 1
    return cechy


def cechy_granicy(baza, dzialka):
    granica = json.dumps({"type": "MultiPolygon", "coordinates": dzialka["granica"]})
    pole, obwod, x, y, poprawna = baza.execute(
        """
        WITH g AS (SELECT ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 2180) AS geom)
        SELECT ST_Area(geom), ST_Perimeter(geom), ST_X(ST_Centroid(geom)), ST_Y(ST_Centroid(geom)), ST_IsValid(geom)
        FROM g
        """,
        (granica,),
    ).fetchone()
    if not poprawna or pole <= 0:
        raise ValueError("Granica działki jest niepoprawna")

    zwartosc = None
    if obwod > 0:
        zwartosc = 4 * math.pi * pole / obwod**2

    cechy = {"x_2180": x, "y_2180": y, "wskaznik_zwartosci": zwartosc}
    return cechy, pole


def odleglosc(baza, warstwa, punkt):
    zapytanie = sql.SQL(
        """
        SELECT ST_Distance(geometry, ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180))
        FROM {}
        ORDER BY geometry <-> ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180)
        LIMIT 1
        """
    ).format(sql.Identifier("dane", "osm_" + warstwa))
    wiersz = baza.execute(zapytanie, punkt).fetchone()
    if wiersz is None:
        return None
    return wiersz[0]


def liczba_w_promieniu(baza, warstwa, punkt, promien):
    zapytanie = sql.SQL(
        """
        SELECT count(*)
        FROM {}
        WHERE geometry && ST_Expand(ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180), {promien})
          AND (x - %(x)s)^2 + (y - %(y)s)^2 <= {promien} * {promien}
        """
    ).format(sql.Identifier("dane", "osm_" + warstwa), promien=sql.Literal(promien))
    return baza.execute(zapytanie, punkt).fetchone()[0]


def pokrycie(baza, warstwa, punkt, promien=500):
    zapytanie = sql.SQL(
        """
        WITH kolo AS (SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180), {}, 'quad_segs=16') AS k)
        SELECT (
            SELECT coalesce(ST_Area(ST_Union(ST_Intersection(t.geometry, kolo.k))), 0)
            FROM {} AS t
            WHERE ST_Intersects(t.geometry, kolo.k)
        ) / ST_Area(kolo.k)
        FROM kolo
        """
    ).format(sql.Literal(promien), sql.Identifier("dane", "osm_" + warstwa))
    udzial = baza.execute(zapytanie, punkt).fetchone()[0]
    return min(max(udzial, 0), 1)


def drogi(baza, punkt):
    return {
        "odl_droga_dowolna_m": odleglosc(baza, "drogi", punkt),
        "odl_droga_utwardzona_m": odleglosc(baza, "utwardzone", punkt),
    }


def zabudowa(baza, punkt):
    return {
        "odl_najblizszy_budynek_m": odleglosc(baza, "budynki", punkt),
        "liczba_budynkow_1000m": liczba_w_promieniu(baza, "budynki", punkt, 1000),
    }


def las_i_uslugi(baza, punkt):
    return {
        "udzial_lasu_500m": pokrycie(baza, "las", punkt),
        "liczba_poi_1km": liczba_w_promieniu(baza, "poi", punkt, 1000),
    }


def miasta(baza, punkt):
    return {"odl_miasto_pow_50k_m": odleglosc(baza, "miasta_50k", punkt)}


def parametry_sasiedztwa(cechy, dzialka):
    # Narysowana granica nie ma numeru działki, więc nie ma też jej wcześniejszych sprzedaży.
    identyfikator = None
    if dzialka["zrodloGranicy"] == "uldk":
        identyfikator = dzialka["identyfikator"]
    return {
        "x": cechy["x_2180"],
        "y": cechy["y_2180"],
        "dzien": date.fromisoformat(dzialka["dataWyceny"]),
        "dzialka": identyfikator,
        "uzytek": cechy["dzi_sposob_uzyt"],
        "gmina": cechy["teryt_gmina"],
        "obreb": dzialka["terytObrebu"],
    }


def ceny_w_promieniu(baza, parametry):
    mediana_5km, mediana_2km, liczba_2km, mediana_2km_uzytek = baza.execute(
        """
        SELECT
            percentile_cont(0.5) WITHIN GROUP (ORDER BY cena_m2),
            percentile_cont(0.5) WITHIN GROUP (ORDER BY cena_m2) FILTER (WHERE odleglosc <= 2000),
            count(*) FILTER (WHERE odleglosc <= 2000),
            percentile_cont(0.5) WITHIN GROUP (ORDER BY cena_m2) FILTER (WHERE odleglosc <= 2000 AND dzi_sposob_uzyt = %(uzytek)s)
        FROM (
            SELECT cena_m2, dzi_sposob_uzyt, ST_Distance(srodek, ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180)) AS odleglosc
            FROM dane.transakcje
            WHERE ST_DWithin(srodek, ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180), 5000)
              AND dok_data < %(dzien)s
              AND dok_data >= %(dzien)s - interval '24 months'
              AND dzi_id_dzialki IS DISTINCT FROM %(dzialka)s
        ) AS wokol
        """,
        parametry,
    ).fetchone()
    return {
        "mediana_cena_m2_2km_ten_sam_uzytek": mediana_2km_uzytek,
        "mediana_cena_m2_2km_24m": mediana_2km,
        "mediana_cena_m2_5km_24m": mediana_5km,
        "liczba_transakcji_2km_24m": liczba_2km,
    }


def najblizsza_transakcja(baza, parametry):
    wiersz = baza.execute(
        """
        SELECT ST_Distance(srodek, ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180))
        FROM dane.transakcje
        WHERE dok_data < %(dzien)s AND dzi_id_dzialki IS DISTINCT FROM %(dzialka)s
        ORDER BY srodek <-> ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180)
        LIMIT 1
        """,
        parametry,
    ).fetchone()

    odleglosc_do_transakcji = None
    if wiersz is not None:
        odleglosc_do_transakcji = wiersz[0]
    return {"odl_najblizsza_transakcja_m": odleglosc_do_transakcji}


def ceny_w_obszarze(baza, parametry):
    mediana_gmina, ostatni_rok, poprzedni_rok = baza.execute(
        """
        SELECT
            percentile_cont(0.5) WITHIN GROUP (ORDER BY cena_m2),
            percentile_cont(0.5) WITHIN GROUP (ORDER BY cena_m2) FILTER (WHERE dok_data >= %(dzien)s - interval '12 months'),
            percentile_cont(0.5) WITHIN GROUP (ORDER BY cena_m2) FILTER (
                WHERE dok_data >= %(dzien)s - interval '24 months' AND dok_data < %(dzien)s - interval '12 months'
            )
        FROM dane.transakcje
        WHERE teryt_gmina = %(gmina)s AND dok_data < %(dzien)s AND dzi_id_dzialki IS DISTINCT FROM %(dzialka)s
        """,
        parametry,
    ).fetchone()

    mediana_obreb = baza.execute(
        """
        SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY cena_m2)
        FROM dane.transakcje
        WHERE teryt_obreb = %(obreb)s AND dok_data < %(dzien)s AND dzi_id_dzialki IS DISTINCT FROM %(dzialka)s
        """,
        parametry,
    ).fetchone()[0]

    trend = None
    if ostatni_rok is not None and poprzedni_rok is not None:
        trend = ostatni_rok / poprzedni_rok - 1

    return {
        "mediana_cena_m2_obreb": mediana_obreb,
        "mediana_cena_m2_gmina": mediana_gmina,
        "trend_cen_gmina_12m": trend,
    }


ETAPY_OSM = [drogi, zabudowa, las_i_uslugi, miasta]
ETAPY_SASIEDZTWA = [ceny_w_promieniu, najblizsza_transakcja, ceny_w_obszarze]
