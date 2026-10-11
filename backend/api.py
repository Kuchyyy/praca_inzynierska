import json
import math
import time

import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config
from wycena.baza import polacz
from wycena.cechy import ETAPY_OSM, ETAPY_SASIEDZTWA, cechy_formularza, cechy_granicy, parametry_sasiedztwa
from wycena.model import objasniacz, przedzial, przewidz, wczytaj, wyjasnij
from wycena.okolica import historia_gminy, percentyle, podpowiedz, poprzednie_sprzedaze, transakcje_wokol

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
    # Jedna linia JSON na zdarzenie. Panel czyta je na bieżąco.
    return json.dumps(dane, ensure_ascii=False) + "\n"


def wynik_modeli(cechy, modele):
    _, opis = wczytaj()
    najlepszy = next(m for m in modele if m["nazwa"] == opis["najlepszy"])
    wycena = {"cenaM2": najlepszy["cenaM2"], "model": najlepszy["nazwa"]}
    wycena.update(przedzial(najlepszy["cenaM2"], cechy))
    return wycena


def uwagi(cechy, wycena, modele, dzialka, pole, poprzednie):
    lista = []

    liczba_2km = cechy["liczba_transakcji_2km_24m"]
    lista.append({"tekst": f"{liczba_2km} transakcji w 2 km z ostatnich 24 mies.", "dobrze": liczba_2km >= 10})

    trend = cechy["trend_cen_gmina_12m"]
    if trend is not None:
        lista.append({"tekst": f"Trend cen w gminie: {liczba(trend * 100, 1)}% r/r", "dobrze": True})

    # Regresje liniowe są wyraźnie słabsze, więc zgodność sprawdzamy na trzech najlepszych modelach.
    najlepsze = sorted(modele, key=lambda m: m["mae"])[:3]
    ceny = [m["cenaM2"] for m in najlepsze]
    rozrzut = (max(ceny) - min(ceny)) / wycena["cenaM2"] * 100
    lista.append({"tekst": f"Trzy najlepsze modele różnią się o {liczba(rozrzut)}%", "dobrze": rozrzut <= 25})

    powierzchnia = cechy["powierzchnia_m2"]
    if not 100 <= powierzchnia <= 200000:
        lista.append({"tekst": "Powierzchnia poza zakresem danych treningowych (100–200 000 m²)", "dobrze": False})
    if abs(pole / powierzchnia - 1) > 0.2:
        lista.append({"tekst": f"Pole z granicy ({liczba(pole)} m²) różni się od podanej powierzchni", "dobrze": False})
    if dzialka["zrodloGranicy"] == "rysunek":
        lista.append({"tekst": "Granica narysowana ręcznie, nie z ewidencji", "dobrze": False})

    for sprzedaz in poprzednie:
        lista.append({"tekst": f"Ta działka była sprzedana {sprzedaz['data']}: {liczba(sprzedaz['cenaM2'], 2)} zł/m²", "dobrze": True})
    return lista


def wyjasnienia(cechy):
    # Wkład cech osobno dla każdego modelu; panel przełącza się między nimi.
    _, opis = wczytaj()
    return [wyjasnij(cechy, metryki) for metryki in opis["modele"]]


def przebieg(dzialka):
    # Kolejne kroki wyceny. Po każdym wysyłamy postęp, na końcu cały wynik.
    poczatek = time.monotonic()
    kroki = []

    def koniec_kroku(numer, wynik, start):
        kroki.append({"numer": numer, "wynik": wynik, "czas": time.monotonic() - start})
        return wiersz({"krok": numer, "wynik": wynik, "czas": kroki[-1]["czas"]})

    try:
        _, opis = wczytaj()
        with polacz() as baza:
            print(f"Wycena: {dzialka['identyfikator']}", flush=True)

            # 1. Dane z formularza: TERYT, czas, przeznaczenie, prawo, sprzedający.
            start = time.monotonic()
            cechy = cechy_formularza(dzialka)
            nazwa = "granica narysowana" if dzialka["zrodloGranicy"] == "rysunek" else dzialka["identyfikator"]
            yield koniec_kroku(1, nazwa, start)

            # 2. Granica: środek, pole i zwartość w EPSG:2180.
            start = time.monotonic()
            nowe, pole = cechy_granicy(baza, dzialka)
            cechy.update(nowe)
            yield koniec_kroku(2, f"{liczba(pole)} m² · zwartość {liczba(cechy['wskaznik_zwartosci'], 2)}", start)

            # 3. Otoczenie z OSM, 27 cech w czterech grupach.
            start = time.monotonic()
            punkt = {"x": cechy["x_2180"], "y": cechy["y_2180"]}
            for numer, etap in enumerate(ETAPY_OSM):
                cechy.update(etap(baza, punkt))
                yield wiersz({"krok": 3, "podkrok": numer})
            opis_osm = f"droga {liczba(cechy['odl_droga_dowolna_m'])} m · {liczba(cechy['liczba_budynkow_1000m'])} bud. / 1 km"
            yield koniec_kroku(3, opis_osm, start)

            # 4. Sąsiedztwo cenowe z transakcji sprzed daty wyceny.
            start = time.monotonic()
            parametry = parametry_sasiedztwa(cechy, dzialka)
            for numer, etap in enumerate(ETAPY_SASIEDZTWA):
                cechy.update(etap(baza, parametry))
                yield wiersz({"krok": 4, "podkrok": numer})
            liczba_2km = cechy["liczba_transakcji_2km_24m"]
            if liczba_2km:
                opis_cen = f"{liczba_2km} w 2 km · mediana {liczba(cechy['mediana_cena_m2_2km_24m'])} zł/m²"
            else:
                opis_cen = f"brak w 2 km · gmina {liczba(cechy['mediana_cena_m2_gmina'])} zł/m²"
            yield koniec_kroku(4, opis_cen, start)

            # 5. Wszystkie modele na tych samych cechach.
            start = time.monotonic()
            modele = []
            for numer, metryki in enumerate(opis["modele"]):
                modele.append(przewidz(cechy, metryki))
                yield wiersz({"krok": 5, "podkrok": numer})
            ceny = [m["cenaM2"] for m in modele]
            yield koniec_kroku(5, f"{liczba(min(ceny))}–{liczba(max(ceny))} zł/m²", start)

            # 6. Wynik: przedział, wyjaśnienie i tło rynku.
            start = time.monotonic()
            wycena = wynik_modeli(cechy, modele)
            yield wiersz({"krok": 6, "podkrok": 0})
            wyjasnienia_modeli = wyjasnienia(cechy)
            yield wiersz({"krok": 6, "podkrok": 1})
            historia = historia_gminy(baza, parametry)
            transakcje = transakcje_wokol(baza, parametry)
            poprzednie = poprzednie_sprzedaze(baza, parametry)
            yield wiersz({"krok": 6, "podkrok": 2})
            na_tle = percentyle(baza, cechy, opis["liczbowe"])
            wycena["uwagi"] = uwagi(cechy, wycena, modele, dzialka, pole, poprzednie)
            yield koniec_kroku(6, f"{liczba(wycena['cenaM2'], 2)} zł/m²", start)

        wynik = {
            "cechy": cechy,
            "wycena": wycena,
            "modele": modele,
            "wyjasnienia": wyjasnienia_modeli,
            "naTle": na_tle,
            "historia": historia,
            "transakcje": transakcje,
            "poprzednie": poprzednie,
            "kroki": kroki,
            "czas": time.monotonic() - poczatek,
        }
        print(f"Gotowe: {wycena['cenaM2']:.2f} zl/m2 w {wynik['czas']:.1f} s", flush=True)
        yield wiersz({"wynik": wynik})

    except Exception as blad:
        print(f"Blad wyceny: {blad!r}", flush=True)
        yield wiersz({"blad": str(blad)})


@app.get("/api/zdrowie")
def zdrowie():
    with polacz() as baza:
        transakcje = baza.execute("SELECT count(*) FROM dane.transakcje").fetchone()[0]
    _, opis = wczytaj()
    return {"transakcje": transakcje, "najlepszy": opis["najlepszy"]}


@app.get("/api/model")
def opis_modelu():
    # Wszystko o wytrenowanych modelach: metryki, ważność cech i statystyki z treningu.
    _, opis = wczytaj()
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
    # Tryb „co jeśli”: te same modele na cechach zmienionych w panelu.
    _, opis = wczytaj()
    cechy = przeliczenie.cechy
    # Logarytm powierzchni zawsze zgodny z powierzchnią wpisaną w panelu.
    if cechy.get("powierzchnia_m2"):
        cechy["log_powierzchnia"] = math.log(cechy["powierzchnia_m2"])
    modele = [przewidz(cechy, metryki) for metryki in opis["modele"]]
    return {"wycena": wynik_modeli(cechy, modele), "modele": modele, "wyjasnienia": wyjasnienia(cechy)}


if __name__ == "__main__":
    print("Wczytuję modele...", flush=True)
    _, opis = wczytaj()
    for metryki in opis["modele"]:
        if metryki["nazwa"] not in opis["srednie_kolumn"]:
            objasniacz(metryki["nazwa"])
    uvicorn.run(app, host="127.0.0.1", port=config.API_PORT)
