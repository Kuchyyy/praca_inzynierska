import csv
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from psycopg import sql

import config
from etl.wczytanie_i_czyszczenie_cech.pozostale import PRZEZNACZENIA
from model.trenuj import KOSZYKI_TRANSAKCJI, koszyk
from wycena.baza import polacz
from wycena.cechy import policz_cechy
from wycena.model import przedzial, przewidz, wczytaj


def wylosuj_sprzedaze(baza, cechy, dol, gora, liczba):
    # Sprzedaże z testu w zakresie cen z treningu. Kolejność po skrócie klucza: ten sam wynik za każdym razem.
    zapytanie = sql.SQL(
        """
        SELECT klucz_transakcji, dzi_id_dzialki, teryt_obreb, ST_AsGeoJSON(ST_Transform(geometry, 4326)),
               powierzchnia_m2, dzi_sposob_uzyt, dzi_przezn_wmpzp, nier_prawo, tran_sprzedajacy,
               dok_data::date, cena_m2, {}
        FROM dane.transakcje
        WHERE zbior = 'test'
          AND cena_m2 BETWEEN %s AND %s
          AND dzi_sposob_uzyt IS NOT NULL AND nier_prawo IS NOT NULL AND tran_sprzedajacy IS NOT NULL
          AND ST_GeometryType(geometry) IN ('ST_Polygon', 'ST_MultiPolygon')
        ORDER BY md5(klucz_transakcji)
        LIMIT %s
        """
    ).format(sql.SQL(", ").join(sql.Identifier(cecha) for cecha in cechy))
    return baza.execute(zapytanie, (dol, gora, liczba)).fetchall()


def podsumuj(ramka, kolumna_wyceny):
    blad = (ramka[kolumna_wyceny] - ramka.cena_m2).abs()
    return {
        "liczba": len(ramka),
        "mae": float(blad.mean()),
        "mediana_bledu_procent": float((blad / ramka.cena_m2).median() * 100),
    }


def backtest():
    _, opis = wczytaj()
    najlepszy = next(m for m in opis["modele"] if m["nazwa"] == opis["najlepszy"])
    poczatek = time.monotonic()

    wiersze = []
    with polacz() as baza:
        sprzedaze = wylosuj_sprzedaze(
            baza, opis["cechy"], opis["progi_ceny"]["dol"], opis["progi_ceny"]["gora"], config.BACKTEST_LICZBA
        )
        print(f"Backtest: {len(sprzedaze):,} sprzedaży z testu, wycena modelem {najlepszy['nazwa']}", flush=True)

        for numer, sprzedaz in enumerate(sprzedaze, 1):
            klucz, identyfikator, obreb, geojson, powierzchnia, uzytek, przezn, prawo, sprzedajacy, dzien, cena = sprzedaz[:11]
            z_etl = dict(zip(opis["cechy"], sprzedaz[11:]))

            # Przeznaczenie z RCN, tak jak w treningu: wpis może mieć kilka kategorii albo żadnej.
            wpisy = {czesc.strip() for czesc in (przezn or "").split(";") if czesc.strip()}
            pierwsze = next((w for w in sorted(wpisy) if w in PRZEZNACZENIA), PRZEZNACZENIA[0])

            geometria = json.loads(geojson)
            granica = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
            dzialka = {
                "identyfikator": identyfikator,
                "zrodloGranicy": "uldk",
                "terytObrebu": obreb,
                "granica": granica,
                "powierzchnia": str(powierzchnia),
                "rodzajGruntu": uzytek,
                "przeznaczenie": pierwsze,
                "prawo": prawo,
                "sprzedajacy": sprzedajacy,
                "dataWyceny": dzien.isoformat(),
            }
            cechy, _, _ = policz_cechy(baza, dzialka)
            for kategoria in PRZEZNACZENIA:
                cechy["przezn_" + kategoria] = int(kategoria in wpisy)
            cechy["przezn_brak_danych"] = int(not wpisy)
            cechy["ma_wpis_przeznaczenia"] = int(bool(wpisy))

            # Ta sama sprzedaż wyceniona na cechach z panelu i na cechach z ETL (referencje sprzed testu).
            wycena_panel = przewidz(cechy, najlepszy)["cenaM2"]
            wycena_etl = przewidz(z_etl, najlepszy)["cenaM2"]
            granice = przedzial(wycena_panel, cechy)

            wiersze.append({
                "klucz_transakcji": klucz,
                "data": dzien.isoformat(),
                "wojewodztwo": cechy["teryt_woj"],
                "rodzaj_gruntu": uzytek,
                "przeznaczenie": ";".join(sorted(wpisy)) if wpisy else "brak wpisu",
                "transakcje_2km": KOSZYKI_TRANSAKCJI[koszyk(cechy["liczba_transakcji_2km_24m"] or 0)],
                "cena_m2": cena,
                "wycena_panel": wycena_panel,
                "wycena_etl": wycena_etl,
                "w_przedziale_80": granice["przedzialOd"] <= cena <= granice["przedzialDo"],
            })

            if numer % 200 == 0:
                print(f"  {numer:,}/{len(sprzedaze):,}, {time.monotonic() - poczatek:.0f} s", flush=True)

    ramka = pd.DataFrame(wiersze)
    panel = podsumuj(ramka, "wycena_panel")
    etl = podsumuj(ramka, "wycena_etl")
    pokrycie = float(ramka.w_przedziale_80.mean() * 100)

    print()
    print(f"Model {najlepszy['nazwa']}, {len(ramka):,} sprzedaży z testu")
    print(f"  cechy z panelu (wszystkie wcześniejsze transakcje): MAE {panel['mae']:7.2f}   mediana błędu {panel['mediana_bledu_procent']:5.1f}%")
    print(f"  cechy z ETL (referencje sprzed {config.TEST_OD}):      MAE {etl['mae']:7.2f}   mediana błędu {etl['mediana_bledu_procent']:5.1f}%")
    print(f"  prawdziwa cena w przedziale 80%: {pokrycie:.1f}% sprzedaży")

    przekroje = {}
    for kolumna in ["wojewodztwo", "rodzaj_gruntu", "transakcje_2km"]:
        przekroje[kolumna] = {}
        print()
        print(f"{kolumna:<32} {'liczba':>7} {'MAE':>8} {'mediana błędu':>14} {'w przedziale':>13}")
        for wartosc, grupa in ramka.groupby(kolumna):
            wynik = podsumuj(grupa, "wycena_panel")
            wynik["w_przedziale_procent"] = float(grupa.w_przedziale_80.mean() * 100)
            przekroje[kolumna][str(wartosc)] = wynik
            print(f"{str(wartosc):<32} {wynik['liczba']:>7} {wynik['mae']:8.2f} {wynik['mediana_bledu_procent']:13.1f}% {wynik['w_przedziale_procent']:12.1f}%")

    # Przeznaczenie: tylko najczęstsze wpisy, reszta razem.
    najczestsze = ramka.przeznaczenie.value_counts().head(8).index
    ramka["przeznaczenie_grupa"] = np.where(ramka.przeznaczenie.isin(najczestsze), ramka.przeznaczenie, "pozostałe")
    przekroje["przeznaczenie"] = {}
    print()
    print(f"{'przeznaczenie':<48} {'liczba':>7} {'MAE':>8} {'mediana błędu':>14}")
    for wartosc, grupa in ramka.groupby("przeznaczenie_grupa"):
        wynik = podsumuj(grupa, "wycena_panel")
        przekroje["przeznaczenie"][wartosc] = wynik
        print(f"{wartosc[:48]:<48} {wynik['liczba']:>7} {wynik['mae']:8.2f} {wynik['mediana_bledu_procent']:13.1f}%")

    katalog = Path(config.SCIEZKA_BACKTESTU)
    katalog.mkdir(parents=True, exist_ok=True)
    with (katalog / "wyceny.csv").open("w", newline="") as wyjscie:
        zapis = csv.DictWriter(wyjscie, fieldnames=list(wiersze[0]))
        zapis.writeheader()
        zapis.writerows(wiersze)
    raport = {
        "model": najlepszy["nazwa"],
        "panel": panel,
        "etl": etl,
        "pokrycie_przedzialu_80_procent": pokrycie,
        "przekroje": przekroje,
        "czas_sekundy": round(time.monotonic() - poczatek),
    }
    (katalog / "podsumowanie.json").write_text(json.dumps(raport, ensure_ascii=False, indent=2))
    print()
    print(f"Wyniki: {katalog}")


if __name__ == "__main__":
    backtest()
