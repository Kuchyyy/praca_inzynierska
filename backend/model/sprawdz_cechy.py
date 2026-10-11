import json
import time
from pathlib import Path

from psycopg import sql

import config
from etl.wczytanie_i_czyszczenie_cech.pozostale import PRZEZNACZENIA
from wycena.baza import polacz
from wycena.cechy import policz_cechy


def tolerancja(cecha):
    # Granica przechodzi przez EPSG:4326 i z powrotem, więc środek może się
    # przesunąć o milimetry. Odległości porównujemy więc z zapasem pół metra.
    if cecha.endswith("_m") or cecha in {"x_2180", "y_2180"}:
        return 0.5
    if cecha.startswith("udzial_") or cecha == "wskaznik_zwartosci":
        return 0.001
    if cecha.startswith("mediana_"):
        return 0.01
    return 1e-6


def wylosuj_transakcje(baza, cechy, liczba):
    # Transakcje treningowe z jednym znanym przeznaczeniem, bo formularz pozwala wybrać jedno.
    # Kolejność po skrócie klucza: ten sam wynik przy każdym uruchomieniu.
    zapytanie = sql.SQL(
        """
        SELECT klucz_transakcji, dzi_id_dzialki, teryt_obreb, ST_AsGeoJSON(ST_Transform(geometry, 4326)),
               powierzchnia_m2, dzi_sposob_uzyt, trim(dzi_przezn_wmpzp), nier_prawo, tran_sprzedajacy,
               dok_data::date, {}
        FROM dane.transakcje
        WHERE zbior = 'trening'
          AND dzi_sposob_uzyt IS NOT NULL AND nier_prawo IS NOT NULL AND tran_sprzedajacy IS NOT NULL
          AND trim(coalesce(dzi_przezn_wmpzp, '')) <> '' AND dzi_przezn_wmpzp NOT LIKE '%%;%%'
          AND ST_GeometryType(geometry) IN ('ST_Polygon', 'ST_MultiPolygon')
        ORDER BY md5(klucz_transakcji)
        LIMIT %s
        """
    ).format(sql.SQL(", ").join(sql.Identifier(cecha) for cecha in cechy))
    return baza.execute(zapytanie, (liczba,)).fetchall()


def porownaj(wynik, cecha, z_etl, z_panelu, klucz):
    if z_etl is None and z_panelu is None:
        wynik["zgodne"] += 1
        return
    if z_etl is None:
        wynik["brak_w_etl"] += 1
        return
    if z_panelu is None:
        wynik["brak_w_panelu"] += 1
        return

    if isinstance(z_etl, str) or isinstance(z_panelu, str):
        zgodne = str(z_etl) == str(z_panelu)
    else:
        roznica = abs(float(z_etl) - float(z_panelu))
        wynik["max_roznica"] = max(wynik["max_roznica"], roznica)
        zgodne = roznica <= tolerancja(cecha)

    if zgodne:
        wynik["zgodne"] += 1
        return
    wynik["rozne"] += 1
    if len(wynik["przyklady"]) < 3:
        wynik["przyklady"].append({"klucz": klucz, "etl": z_etl, "panel": z_panelu})


def sprawdz_cechy():
    kontrakt = json.loads((Path(config.SCIEZKA_AUDYT) / "cechy_modelu.json").read_text())
    cechy = kontrakt["warianty"][config.WARIANT_MODELU]["cechy"]
    poczatek = time.monotonic()

    wyniki = {}
    for cecha in cechy:
        wyniki[cecha] = {"zgodne": 0, "rozne": 0, "brak_w_etl": 0, "brak_w_panelu": 0, "max_roznica": 0.0, "przyklady": []}

    sprawdzone = 0
    with polacz() as baza:
        wiersze = wylosuj_transakcje(baza, cechy, config.SPRAWDZ_CECHY_LICZBA)
        print(f"Sprawdzam {len(wiersze):,} transakcji treningowych, {len(cechy)} cech", flush=True)

        for numer, wiersz in enumerate(wiersze, 1):
            klucz, identyfikator, obreb, geojson, powierzchnia, uzytek, przeznaczenie, prawo, sprzedajacy, dzien = wiersz[:10]
            if przeznaczenie not in PRZEZNACZENIA:
                continue

            # Tę samą transakcję wyceniamy jak nową działkę w dniu jej sprzedaży.
            geometria = json.loads(geojson)
            granica = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
            dzialka = {
                "identyfikator": identyfikator,
                "zrodloGranicy": "uldk",
                "terytObrebu": obreb,
                "granica": granica,
                "powierzchnia": str(powierzchnia),
                "rodzajGruntu": uzytek,
                "przeznaczenie": przeznaczenie,
                "prawo": prawo,
                "sprzedajacy": sprzedajacy,
                "dataWyceny": dzien.isoformat(),
            }
            z_panelu, _, _ = policz_cechy(baza, dzialka)
            z_etl = dict(zip(cechy, wiersz[10:]))
            for cecha in cechy:
                porownaj(wyniki[cecha], cecha, z_etl[cecha], z_panelu.get(cecha), klucz)
            sprawdzone += 1

            if numer % 100 == 0:
                print(f"  {numer:,}/{len(wiersze):,}, {time.monotonic() - poczatek:.0f} s", flush=True)

    print()
    print(f"{'cecha':<45} {'zgodne':>8} {'różne':>6} {'brak ETL':>9} {'brak panel':>11} {'max różnica':>13}")
    kolejnosc = sorted(cechy, key=lambda c: wyniki[c]["zgodne"])
    for cecha in kolejnosc:
        w = wyniki[cecha]
        procent = w["zgodne"] / sprawdzone * 100 if sprawdzone else 0
        print(f"{cecha:<45} {procent:7.1f}% {w['rozne']:6} {w['brak_w_etl']:9} {w['brak_w_panelu']:11} {w['max_roznica']:13.4f}")

    pelne = [c for c in cechy if wyniki[c]["zgodne"] == sprawdzone]
    print()
    print(f"W pełni zgodne: {len(pelne)} z {len(cechy)} cech, sprawdzono {sprawdzone:,} transakcji")

    raport = {
        "sprawdzone": sprawdzone,
        "w_pelni_zgodne": len(pelne),
        "cechy": wyniki,
        "czas_sekundy": round(time.monotonic() - poczatek),
    }
    cel = Path(config.SCIEZKA_SPRAWDZENIA_CECH)
    cel.write_text(json.dumps(raport, ensure_ascii=False, indent=2, default=str))
    print(f"Raport: {cel}")


if __name__ == "__main__":
    sprawdz_cechy()
