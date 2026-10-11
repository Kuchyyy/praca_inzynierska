import json
import math
from functools import cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

import config
from model.przygotowanie import przygotuj_wejscia
from model.trenuj import KOSZYKI_TRANSAKCJI, cecha_kolumny, koszyk

PEWNOSC = ["Niska pewność", "Niska pewność", "Średnia pewność", "Wysoka pewność"]


@cache
def wczytaj():
    # Modele ładujemy raz, przy pierwszej wycenie.
    katalog = Path(config.SCIEZKA_MODELU)
    if not katalog.exists():
        raise FileNotFoundError("Brak wytrenowanych modeli. Uruchom: python -m model.trenuj")
    modele = joblib.load(katalog / "modele.joblib")
    opis = json.loads((katalog / "podsumowanie.json").read_text())
    return modele, opis


def wejscie_modelu(cechy):
    _, opis = wczytaj()
    ramka = pd.DataFrame([{nazwa: cechy.get(nazwa) for nazwa in opis["cechy"]}])
    return przygotuj_wejscia(ramka, {"warianty": {"wycena": opis}}, "wycena")


def przewidz(cechy, metryki):
    modele, _ = wczytaj()
    cena = float(modele[metryki["nazwa"]].predict(wejscie_modelu(cechy))[0])
    return {
        "nazwa": metryki["nazwa"],
        "cenaM2": cena,
        "mae": metryki["mae"],
        "rmse": metryki["rmse"],
        "r2": metryki["r2"],
    }


def przedzial(cena, cechy):
    # Na teście 80% prawdziwych cen mieściło się w tych krotnościach wyceny.
    _, opis = wczytaj()
    numer = koszyk(cechy.get("liczba_transakcji_2km_24m") or 0)
    granice = opis["przedzialy"][numer]
    return {
        "przedzialOd": cena * granice["dol"],
        "przedzialDo": cena * granice["gora"],
        "pewnosc": PEWNOSC[numer],
        "koszyk": KOSZYKI_TRANSAKCJI[numer],
    }


@cache
def objasniacz(nazwa):
    # Objaśniacz SHAP budujemy raz na model drzewiasty i trzymamy w pamięci.
    modele, _ = wczytaj()
    potok = modele[nazwa]
    rdzen = potok.regressor_ if hasattr(potok, "regressor_") else potok
    return shap.TreeExplainer(rdzen.named_steps["model"])


def wyjasnij(cechy, metryki):
    # Wkład każdej cechy w wycenę jednego modelu, w zł/m². Start plus suma wkładów
    # daje dokładnie cenę tego modelu.
    modele, opis = wczytaj()
    nazwa = metryki["nazwa"]
    potok = modele[nazwa]
    rdzen = potok.regressor_ if metryki["na_logarytmie"] else potok
    przetwarzanie = rdzen.named_steps["przetwarzanie"]
    model = rdzen.named_steps["model"]
    x = przetwarzanie.transform(wejscie_modelu(cechy))[0]

    if nazwa in opis["srednie_kolumn"]:
        # Regresja: wkład to współczynnik razy odchylenie od średniej działki z treningu.
        srednie = np.array(opis["srednie_kolumn"][nazwa])
        kolumny = model.coef_ * (x - srednie)
        start = float(model.intercept_ + model.coef_ @ srednie)
    else:
        # Drzewa: wartości SHAP liczone dokładnie po strukturze drzew.
        wyjasniacz = objasniacz(nazwa)
        kolumny = wyjasniacz.shap_values(x.reshape(1, -1))[0]
        start = float(np.ravel(wyjasniacz.expected_value)[0])

    # Kolumny po przetworzeniu (0/1, wskaźniki braków, średnie gmin) wracają do swoich cech.
    sumy = dict.fromkeys(opis["cechy"], 0.0)
    for kolumna, wartosc in zip(przetwarzanie.get_feature_names_out(), kolumny):
        sumy[cecha_kolumny(kolumna, opis)] += float(wartosc)

    if metryki["na_logarytmie"]:
        # Model liczy na logarytmie ceny. Wkłady przeliczamy na zł/m² średnią logarytmiczną
        # ceny startowej i końcowej; wtedy dalej sumują się dokładnie do wyceny.
        cena_startowa = math.exp(start)
        cena = math.exp(start + sum(sumy.values()))
        mnoznik = cena
        if abs(math.log(cena) - math.log(cena_startowa)) > 1e-12:
            mnoznik = (cena - cena_startowa) / (math.log(cena) - math.log(cena_startowa))
        for kod in sumy:
            sumy[kod] *= mnoznik
    else:
        cena_startowa = start
        cena = start + sum(sumy.values())

    lista = [{"kod": kod, "wklad": wartosc} for kod, wartosc in sumy.items()]
    lista.sort(key=lambda w: abs(w["wklad"]), reverse=True)
    return {"model": nazwa, "start": cena_startowa, "cena": cena, "wklady": lista}
