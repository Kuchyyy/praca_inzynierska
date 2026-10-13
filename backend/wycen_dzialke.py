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


def wycen(cechy):
    X = pd.DataFrame([{cecha: cechy.get(cecha) for cecha in opis["cechy"]}])
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

        y_pred = model.predict(X)
        if model_name in opis["log_models"]:
            y_pred = np.exp(y_pred)

        modele.append({
            "nazwa": model_name,
            "cenaM2": float(y_pred[0]),
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

   
        sumy = dict.fromkeys(opis["cechy"], 0.0)
        for kolumna, wklad in zip(nazwy_kolumn, wklady_kolumn):
            nazwa = kolumna.split("__", 1)[1].removeprefix("missingindicator_")
            if nazwa not in sumy:
                nazwa = next(c for c in opis["kategoryczne"] if nazwa.startswith(c + "_"))
            sumy[nazwa] += float(wklad)

        if model_name in opis["log_models"]:

            cena_startowa = math.exp(start)
            cena = math.exp(start + sum(sumy.values()))
            mnoznik = cena
            if abs(math.log(cena) - math.log(cena_startowa)) > 1e-12:
                mnoznik = (cena - cena_startowa) / (math.log(cena) - math.log(cena_startowa))
            for cecha in sumy:
                sumy[cecha] *= mnoznik
        else:
            cena_startowa = start
            cena = start + sum(sumy.values())

        wklady = [{"kod": cecha, "wklad": wartosc} for cecha, wartosc in sumy.items()]
        wklady.sort(key=lambda w: abs(w["wklad"]), reverse=True)
        wyjasnienia.append({"model": model_name, "start": cena_startowa, "cena": cena, "wklady": wklady})

    najlepszy = next(m for m in modele if m["nazwa"] == opis["najlepszy"])


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
