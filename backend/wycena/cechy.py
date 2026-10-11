import json
import math
import re
from datetime import date

from psycopg import sql

from etl.cechy_osm.polska import ODLEGLOSCI
from etl.wczytanie_i_czyszczenie_cech.pozostale import PRZEZNACZENIA

# Obręb jak w identyfikatorze działki, np. 126102_9.0001.
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

    # Przy wycenie przeznaczenie pochodzi z formularza: jedna wybrana kategoria.
    for kategoria in PRZEZNACZENIA:
        cechy["przezn_" + kategoria] = int(dzialka["przeznaczenie"] == kategoria)
    cechy["przezn_brak_danych"] = 0
    cechy["ma_wpis_przeznaczenia"] = 1
    return cechy


def cechy_granicy(baza, dzialka):
    # Granica przychodzi z panelu w stopniach. Pole, obwód i środek liczymy
    # w EPSG:2180, tak samo jak w ETL.
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

    cechy = {
        "x_2180": x,
        "y_2180": y,
        "wskaznik_zwartosci": 4 * math.pi * pole / obwod**2 if obwod > 0 else None,
    }
    return cechy, pole


def odleglosc(baza, warstwa, punkt):
    # Najbliższy obiekt z indeksu GiST. Odległość do linii lub krawędzi, jak STRtree w ETL.
    zapytanie = sql.SQL(
        """
        SELECT ST_Distance(geometry, ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180))
        FROM {}
        ORDER BY geometry <-> ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180)
        LIMIT 1
        """
    ).format(sql.Identifier("dane", "osm_" + warstwa))
    wiersz = baza.execute(zapytanie, punkt).fetchone()
    return wiersz[0] if wiersz else None


def liczba_w_promieniach(baza, warstwa, punkt, promienie):
    # Jak cKDTree w ETL: liczymy środki obiektów w promieniu, nie same obrysy.
    liczniki = []
    for promien in promienie:
        liczniki.append(
            sql.SQL("count(*) FILTER (WHERE (x - %(x)s)^2 + (y - %(y)s)^2 <= {})").format(sql.Literal(promien**2))
        )
    zapytanie = sql.SQL(
        """
        SELECT {}
        FROM {}
        WHERE geometry && ST_Expand(ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180), {})
        """
    ).format(sql.SQL(", ").join(liczniki), sql.Identifier("dane", "osm_" + warstwa), sql.Literal(max(promienie)))
    return list(baza.execute(zapytanie, punkt).fetchone())


def pokrycie(baza, warstwa, punkt, promien=500):
    # Część koła zajęta przez warstwę. Nakładające się obszary liczymy raz.
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
    cechy = {}
    for warstwa in ["drogi", "utwardzone", "glowne", "lokalne", "autostrady", "wezly", "przystanki"]:
        cechy[ODLEGLOSCI[warstwa]] = odleglosc(baza, warstwa, punkt)
    return cechy


def zabudowa(baza, punkt):
    cechy = {}
    for warstwa in ["budynki", "mieszkalne"]:
        cechy[ODLEGLOSCI[warstwa]] = odleglosc(baza, warstwa, punkt)

    liczby = liczba_w_promieniach(baza, "budynki", punkt, [250, 500, 1000])
    cechy["liczba_budynkow_250m"] = liczby[0]
    cechy["liczba_budynkow_500m"] = liczby[1]
    cechy["liczba_budynkow_1000m"] = liczby[2]

    cechy["udzial_zabudowy_500m"] = pokrycie(baza, "zabudowa", punkt)
    w_zabudowie = odleglosc(baza, "zabudowa", punkt)
    cechy["czy_w_terenie_zabudowanym"] = None if w_zabudowie is None else float(w_zabudowie == 0)
    return cechy


def przyroda_i_uslugi(baza, punkt):
    cechy = {}
    cechy["udzial_lasu_500m"] = pokrycie(baza, "las", punkt)
    for warstwa in ["woda", "szkoly", "sklepy", "przedszkola"]:
        cechy[ODLEGLOSCI[warstwa]] = odleglosc(baza, warstwa, punkt)
    cechy["liczba_poi_1km"] = liczba_w_promieniach(baza, "poi", punkt, [1000])[0]

    # Jak w ETL: woda w 200 m to zbiornik albo rzeka.
    woda = cechy["odl_woda_m"]
    rzeka = odleglosc(baza, "rzeki", punkt)
    blisko = (woda is not None and woda <= 200) or (rzeka is not None and rzeka <= 200)
    znane = (woda is not None and rzeka is not None) or blisko
    cechy["czy_woda_w_200m"] = float(blisko) if znane else None
    return cechy


def miasta(baza, punkt):
    cechy = {}
    for warstwa in ["miejscowosci", "miasta_10k", "miasta_50k", "wroclaw", "granica"]:
        cechy[ODLEGLOSCI[warstwa]] = odleglosc(baza, warstwa, punkt)

    wiersz = baza.execute(
        """
        SELECT population
        FROM dane.osm_miasta
        ORDER BY geometry <-> ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 2180)
        LIMIT 1
        """,
        punkt,
    ).fetchone()
    cechy["ludnosc_najblizszego_miasta"] = wiersz[0] if wiersz else None
    return cechy


def parametry_sasiedztwa(cechy, dzialka):
    # Wcześniejsze sprzedaże tej samej działki nie są sąsiadami. Narysowana granica nie ma numeru.
    identyfikator = dzialka["identyfikator"] if dzialka["zrodloGranicy"] == "uldk" else None
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
    # Tak jak w ETL: tylko ściśle wcześniejsze dni i okno 24 miesięcy.
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
    # Bez okna czasowego: najbliższa wcześniejsza sprzedaż może być sprzed lat.
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
    return {"odl_najblizsza_transakcja_m": wiersz[0] if wiersz else None}


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


# Kolejność grup obliczeń. Tych samych list używa panel (api.py), żeby liczyć tak samo.
ETAPY_OSM = [drogi, zabudowa, przyroda_i_uslugi, miasta]
ETAPY_SASIEDZTWA = [ceny_w_promieniu, najblizsza_transakcja, ceny_w_obszarze]


def policz_cechy(baza, dzialka):
    # Wszystkie 74 cechy działki bez wysyłania postępu: do testów i skryptów w terminalu.
    cechy = cechy_formularza(dzialka)
    nowe, pole = cechy_granicy(baza, dzialka)
    cechy.update(nowe)

    punkt = {"x": cechy["x_2180"], "y": cechy["y_2180"]}
    for etap in ETAPY_OSM:
        cechy.update(etap(baza, punkt))

    parametry = parametry_sasiedztwa(cechy, dzialka)
    for etap in ETAPY_SASIEDZTWA:
        cechy.update(etap(baza, parametry))

    return cechy, pole, parametry
