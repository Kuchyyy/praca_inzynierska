import json
import math
import socket
import time

import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config
from wycen_dzialke import opis, wycen
from wycena.baza import polacz
from wycena.cechy import ETAPY_OSM, ETAPY_SASIEDZTWA, cechy_formularza, cechy_granicy, parametry_sasiedztwa
from wycena.okolica import percentyle, podpowiedz, poprzednie_sprzedaze, transakcje_wokol

app = FastAPI(title="Wycena działek")


class Dzialka(BaseModel):
    identyfikator: str
    zrodloGranicy: str
    terytObrebu: str
    granica: list
    powierzchnia: str
    rodzajGruntu: str
    przeznaczenie: str
    prawo: str
    sprzedajacy: str
    dataWyceny: str


class Przeliczenie(BaseModel):
    cechy: dict


def liczba(wartosc, miejsca=0):
    if wartosc is None:
        return "—"
    return f"{wartosc:,.{miejsca}f}".replace(",", " ").replace(".", ",")


def wiersz(dane):
    return json.dumps(dane, ensure_ascii=False) + "\n"


def uwagi(cechy, wycena, modele, dzialka, pole, poprzednie):
    lista = []

    liczba_2km = cechy["liczba_transakcji_2km_24m"]
    lista.append({"tekst": f"{liczba_2km} transakcji w 2 km z ostatnich 24 mies.", "dobrze": liczba_2km >= 10})

    trend = cechy["trend_cen_gmina_12m"]
    if trend is not None:
        lista.append({"tekst": f"Trend cen w gminie: {liczba(trend * 100, 1)}% r/r", "dobrze": True})

    najlepsze = sorted(modele, key=lambda m: m["mae"])[:3]
    ceny = [m["cenaM2"] for m in najlepsze]
    rozrzut = (max(ceny) - min(ceny)) / wycena["cenaM2"] * 100
    lista.append({"tekst": f"Trzy najlepsze modele różnią się o {liczba(rozrzut)}%", "dobrze": rozrzut <= 25})

    powierzchnia = cechy["powierzchnia_m2"]
    if not config.POWIERZCHNIA_MIN <= powierzchnia <= config.POWIERZCHNIA_MAX:
        lista.append({"tekst": "Powierzchnia poza zakresem danych treningowych (100–200 000 m²)", "dobrze": False})
    if abs(pole / powierzchnia - 1) > 0.2:
        lista.append({"tekst": f"Pole z granicy ({liczba(pole)} m²) różni się od podanej powierzchni", "dobrze": False})
    if dzialka["zrodloGranicy"] == "rysunek":
        lista.append({"tekst": "Granica narysowana ręcznie, nie z ewidencji", "dobrze": False})

    for sprzedaz in poprzednie:
        dzien = ".".join(reversed(sprzedaz["data"].split("-")))
        lista.append({"tekst": f"Ta działka była sprzedana {dzien}: {liczba(sprzedaz['cenaM2'], 2)} zł/m²", "dobrze": True})
    return lista


def koniec_kroku(kroki, numer, wynik, start):
    czas = time.monotonic() - start
    kroki.append({"numer": numer, "wynik": wynik, "czas": czas})
    return wiersz({"krok": numer, "wynik": wynik, "czas": czas})


def przebieg(dzialka):
    poczatek = time.monotonic()
    kroki = []

    try:
        with polacz() as baza:
            print(f"Wycena: {dzialka['identyfikator']}", flush=True)

            start = time.monotonic()
            cechy = cechy_formularza(dzialka)
            nazwa = "granica narysowana" if dzialka["zrodloGranicy"] == "rysunek" else dzialka["identyfikator"]
            yield koniec_kroku(kroki, 1, nazwa, start)

            start = time.monotonic()
            nowe, pole = cechy_granicy(baza, dzialka)
            cechy.update(nowe)
            yield koniec_kroku(kroki, 2, f"{liczba(pole)} m² · zwartość {liczba(cechy['wskaznik_zwartosci'], 2)}", start)

            start = time.monotonic()
            punkt = {"x": cechy["x_2180"], "y": cechy["y_2180"]}
            for numer, etap in enumerate(ETAPY_OSM):
                cechy.update(etap(baza, punkt))
                yield wiersz({"krok": 3, "podkrok": numer})
            opis_osm = f"droga {liczba(cechy['odl_droga_dowolna_m'])} m · {liczba(cechy['liczba_budynkow_1000m'])} bud. / 1 km"
            yield koniec_kroku(kroki, 3, opis_osm, start)

            start = time.monotonic()
            parametry = parametry_sasiedztwa(cechy, dzialka)
            for numer, etap in enumerate(ETAPY_SASIEDZTWA):
                cechy.update(etap(baza, parametry))
                yield wiersz({"krok": 4, "podkrok": numer})
            if cechy["liczba_transakcji_2km_24m"]:
                opis_cen = f"{cechy['liczba_transakcji_2km_24m']} w 2 km · mediana {liczba(cechy['mediana_cena_m2_2km_24m'])} zł/m²"
            else:
                opis_cen = f"brak w 2 km · gmina {liczba(cechy['mediana_cena_m2_gmina'])} zł/m²"
            yield koniec_kroku(kroki, 4, opis_cen, start)

            start = time.monotonic()
            wycena, modele, wyjasnienia = wycen(cechy)
            for numer in range(len(modele)):
                yield wiersz({"krok": 5, "podkrok": numer})
            ceny = [m["cenaM2"] for m in modele]
            yield koniec_kroku(kroki, 5, f"{liczba(min(ceny))}–{liczba(max(ceny))} zł/m²", start)

            start = time.monotonic()
            yield wiersz({"krok": 6, "podkrok": 0})
            yield wiersz({"krok": 6, "podkrok": 1})
            transakcje = transakcje_wokol(baza, parametry)
            poprzednie = poprzednie_sprzedaze(baza, parametry)
            yield wiersz({"krok": 6, "podkrok": 2})
            na_tle = percentyle(baza, cechy, opis["liczbowe"])
            wycena["uwagi"] = uwagi(cechy, wycena, modele, dzialka, pole, poprzednie)
            yield koniec_kroku(kroki, 6, f"{liczba(wycena['cenaM2'], 2)} zł/m²", start)

        wynik = {
            "cechy": cechy,
            "wycena": wycena,
            "modele": modele,
            "wyjasnienia": wyjasnienia,
            "naTle": na_tle,
            "transakcje": transakcje,
            "poprzednie": poprzednie,
            "kroki": kroki,
            "czas": time.monotonic() - poczatek,
        }
        print(f"Gotowe: {wycena['cenaM2']:.2f} zł/m2 w {wynik['czas']:.1f} s", flush=True)
        yield wiersz({"wynik": wynik})

    except Exception as blad:
        print(f"Błąd wyceny: {blad!r}", flush=True)
        yield wiersz({"blad": str(blad)})


@app.get("/api/zdrowie")
def zdrowie():
    with polacz() as baza:
        transakcje = baza.execute("SELECT count(*) FROM dane.transakcje").fetchone()[0]
    return {"transakcje": transakcje, "najlepszy": opis["najlepszy"]}


@app.get("/api/model")
def opis_modelu():
    return {
        "najlepszy": opis["najlepszy"],
        "modele": opis["modele"],
        "przedzialy": opis["przedzialy"],
        "waznosc": opis["waznosc"],
        "statystyki": opis["statystyki"],
        "bledyGruntow": opis["bledy_gruntow"],
        "uczenie": opis["uczenie"],
        "test": opis["test"],
        "progiCeny": opis["progi_ceny"],
    }


@app.get("/api/podpowiedz")
def podpowiedz_formularza(obreb: str):
    with polacz() as baza:
        return podpowiedz(baza, obreb)


@app.post("/api/wycena")
def wycena(dzialka: Dzialka):
    return StreamingResponse(przebieg(dzialka.model_dump()), media_type="application/x-ndjson")


@app.post("/api/przelicz")
def przelicz(przeliczenie: Przeliczenie):
    cechy = przeliczenie.cechy
    if cechy.get("powierzchnia_m2"):
        cechy["log_powierzchnia"] = math.log(cechy["powierzchnia_m2"])

    wycena, modele, wyjasnienia = wycen(cechy)
    return {"wycena": wycena, "modele": modele, "wyjasnienia": wyjasnienia}


if __name__ == "__main__":
    with socket.socket() as gniazdo:
        if gniazdo.connect_ex(("127.0.0.1", config.API_PORT)) == 0:
            print(f"Port {config.API_PORT} jest zajęty, serwer wyceny pewnie już działa.")
            print("Zatrzymaj stary serwer: pkill -f api.py")
            raise SystemExit(1)

    uvicorn.run(app, host="127.0.0.1", port=config.API_PORT)
