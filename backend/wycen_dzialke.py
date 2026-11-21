import math

import joblib
import numpy as np
import pandas as pd
import shap

import config

PEWNOSC = ["Niska pewność", "Niska pewność", "Średnia pewność", "Wysoka pewność"]

zapis = joblib.load(config.SCIEZKA_MODELU)
preprocessing = zapis["przetwarzanie"]
models = zapis["modele"]
opis = zapis["opis"]

objasniacze = {}
for model_name, model in models.items():
    if not hasattr(model, "coef_"):
        objasniacze[model_name] = shap.TreeExplainer(model)

nazwy_kolumn = preprocessing.get_feature_names_out()

log_dol = math.log(opis["progi_ceny"]["dol"])
log_gora = math.log(opis["progi_ceny"]["gora"])


def wycen(cechy):
    wiersz = {}
    for cecha in opis["cechy"]:
        wiersz[cecha] = cechy.get(cecha)
    X = pd.DataFrame([wiersz])

    for cecha in opis["cechy"]:
        if cecha in opis["kategoryczne"]:
            X[cecha] = X[cecha].astype(object).where(X[cecha].notna(), np.nan)
        else:
            X[cecha] = pd.to_numeric(X[cecha]).astype(float)

    X = preprocessing.transform(X)
    x = X[0]

    modele = []
    wyjasnienia = []

    for metryki in opis["modele"]:
        model_name = metryki["nazwa"]
        model = models[model_name]

        y_pred = np.exp(np.clip(model.predict(X), log_dol, log_gora))
        cena_modelu = float(y_pred[0])

        modele.append({
            "nazwa": model_name,
            "cenaM2": cena_modelu,
            "mae": metryki["mae"],
            "rmse": metryki["rmse"],
            "r2": metryki["r2"],
        })

        if hasattr(model, "coef_"):
            srednia = np.array(opis["srednia_dzialka"])
            wklady_kolumn = model.coef_ * (x - srednia)
            start = float(model.intercept_ + model.coef_ @ srednia)
        else:
            wklady_kolumn = objasniacze[model_name].shap_values(X)[0]
            start = float(np.ravel(objasniacze[model_name].expected_value)[0])

        sumy = {}
        for cecha in opis["cechy"]:
            sumy[cecha] = 0.0

        for kolumna, wklad in zip(nazwy_kolumn, wklady_kolumn):
            nazwa = kolumna.split("__", 1)[1]
            nazwa = nazwa.removeprefix("missingindicator_")
            if nazwa not in sumy:
                for cecha in opis["kategoryczne"]:
                    if nazwa.startswith(cecha + "_"):
                        nazwa = cecha
            sumy[nazwa] += float(wklad)

        suma = sum(sumy.values())
        cena_startowa = math.exp(start)
        cena = math.exp(min(max(start + suma, log_dol), log_gora))
        mnoznik = cena
        if abs(suma) > 1e-12:
            mnoznik = (cena - cena_startowa) / suma
        for cecha in sumy:
            sumy[cecha] = sumy[cecha] * mnoznik

        wklady = []
        for cecha, wartosc in sumy.items():
            wklady.append({"kod": cecha, "wklad": wartosc})
        wklady.sort(key=lambda w: abs(w["wklad"]), reverse=True)

        wyjasnienia.append({"model": model_name, "start": cena_startowa, "cena": cena, "wklady": wklady})

    for model in modele:
        if model["nazwa"] == opis["najlepszy"]:
            najlepszy = model

    liczba_transakcji = cechy.get("liczba_transakcji_2km_24m") or 0
    numer = int(np.digitize(liczba_transakcji, opis["koszyki"])) - 1
    granice = opis["przedzialy"][numer]

    wycena = {
        "cenaM2": najlepszy["cenaM2"],
        "model": najlepszy["nazwa"],
        "przedzialOd": najlepszy["cenaM2"] * granice["dol"],
        "przedzialDo": najlepszy["cenaM2"] * granice["gora"],
        "pewnosc": PEWNOSC[numer],
        "koszyk": opis["koszyki"][numer],
    }

    return wycena, modele, wyjasnienia
