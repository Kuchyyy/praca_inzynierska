import csv
import json
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import joblib
import pandas as pd
from shapely import wkt
from shapely.geometry import MultiPolygon, mapping

import config
from model.przygotowanie import przygotuj_wejscia
from wycena.baza import polacz
from wycena.cechy import cechy_granicy, policz_cechy
from wycena.model import przewidz, wczytaj


def granica_dzialki(baza, identyfikator):
    # Najpierw granica z bazy (działka była sprzedana), w przeciwnym razie z ULDK.
    wiersz = baza.execute(
        """
        SELECT ST_AsGeoJSON(ST_Transform(geometry, 4326))
        FROM dane.transakcje
        WHERE dzi_id_dzialki = %s AND ST_GeometryType(geometry) IN ('ST_Polygon', 'ST_MultiPolygon')
        ORDER BY dok_data DESC
        LIMIT 1
        """,
        (identyfikator,),
    ).fetchone()
    if wiersz:
        geometria = json.loads(wiersz[0])
        zrodlo = "baza"
    else:
        adres = "https://uldk.gugik.gov.pl/?" + urllib.parse.urlencode(
            {"request": "GetParcelById", "id": identyfikator, "result": "geom_wkt", "srid": "4326"}
        )
        linie = urllib.request.urlopen(adres, timeout=30).read().decode().strip().splitlines()
        if len(linie) < 2 or linie[0].startswith("-1"):
            raise ValueError(f"ULDK nie zna działki {identyfikator}")
        ksztalt = wkt.loads(linie[1].split(";", 1)[-1])
        if ksztalt.geom_type == "Polygon":
            ksztalt = MultiPolygon([ksztalt])
        geometria = mapping(ksztalt)
        zrodlo = "ULDK"

    granica = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
    return granica, zrodlo


def wczytaj_eksperymenty():
    katalog = Path(config.SCIEZKA_EKSPERYMENTOW)
    eksperymenty = []
    for plik in sorted(katalog.glob("*/opis.json")):
        opis = json.loads(plik.read_text())
        eksperymenty.append((opis, joblib.load(plik.parent / "modele.joblib")))
    return eksperymenty


def wycen_przyklady():
    przyklady = json.loads(Path(config.SCIEZKA_PRZYKLADOW).read_text())
    _, opis_glowny = wczytaj()
    eksperymenty = wczytaj_eksperymenty()
    print(f"{len(przyklady)} działek, główne modele i {len(eksperymenty)} eksperymentów", flush=True)

    wiersze = []
    with polacz() as baza:
        for przyklad in przyklady:
            identyfikator = przyklad["identyfikator"]
            granica, zrodlo = granica_dzialki(baza, identyfikator)
            _, pole = cechy_granicy(baza, {"granica": granica})

            # Brakujące pola formularza uzupełniamy najczęstszymi wartościami z RCN.
            dzialka = {
                "identyfikator": identyfikator,
                "zrodloGranicy": "uldk",
                "terytObrebu": ".".join(identyfikator.split(".")[:2]),
                "granica": granica,
                "powierzchnia": str(przyklad.get("powierzchnia") or round(pole)),
                "rodzajGruntu": przyklad["rodzajGruntu"],
                "przeznaczenie": przyklad["przeznaczenie"],
                "prawo": przyklad.get("prawo", "wlasnoscNieruchomosciGruntowej"),
                "sprzedajacy": przyklad.get("sprzedajacy", "osobaFizyczna"),
                "dataWyceny": przyklad.get("dataWyceny") or date.today().isoformat(),
            }
            cechy, _, _ = policz_cechy(baza, dzialka)
            powierzchnia = cechy["powierzchnia_m2"]

            print()
            print(f"{identyfikator} · {powierzchnia:,.0f} m² · {dzialka['rodzajGruntu']} · {dzialka['przeznaczenie']} · granica z: {zrodlo}")
            if przyklad.get("opis"):
                print(f"  {przyklad['opis']}")

            wyceny = []
            for metryki in opis_glowny["modele"]:
                cena = przewidz(cechy, metryki)["cenaM2"]
                wyceny.append(("główne modele", metryki["nazwa"], len(opis_glowny["cechy"]), cena))

            # Model z eksperymentu dostaje tylko te cechy, na których się uczył.
            for opis, modele in eksperymenty:
                ramka = pd.DataFrame([{c: cechy.get(c) for c in opis["cechy"]}])
                x = przygotuj_wejscia(ramka, {"warianty": {"eksperyment": opis}}, "eksperyment")
                for nazwa_modelu, potok in modele.items():
                    wyceny.append((opis["nazwa"], nazwa_modelu, len(opis["cechy"]), float(potok.predict(x)[0])))

            for zestaw, nazwa_modelu, liczba_cech, cena in wyceny:
                print(f"  {zestaw:<20} {nazwa_modelu:<18} {liczba_cech:>3} cech  {cena:9.2f} zł/m²  {cena * powierzchnia:>14,.0f} zł")
                wiersze.append({
                    "dzialka": identyfikator,
                    "data_wyceny": dzialka["dataWyceny"],
                    "zestaw": zestaw,
                    "model": nazwa_modelu,
                    "liczba_cech": liczba_cech,
                    "cena_m2": round(cena, 2),
                    "wartosc": round(cena * powierzchnia),
                })

    katalog = Path(config.SCIEZKA_EKSPERYMENTOW)
    katalog.mkdir(parents=True, exist_ok=True)
    plik = katalog / "wyceny_przykladow.csv"
    with plik.open("w", newline="") as wyjscie:
        zapis = csv.DictWriter(wyjscie, fieldnames=list(wiersze[0]))
        zapis.writeheader()
        zapis.writerows(wiersze)
    print()
    print(f"Tabela: {plik}")


if __name__ == "__main__":
    wycen_przyklady()
