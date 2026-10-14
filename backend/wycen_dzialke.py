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
    # KROK 1. Tabelka z jednym wierszem: cechy działki w tej samej kolejności co przy treningu.
    wiersz = {}
    for cecha in opis["cechy"]:
        wiersz[cecha] = cechy.get(cecha)
    X = pd.DataFrame([wiersz])

    for cecha in opis["cechy"]:
        if cecha in opis["kategoryczne"]:
            X[cecha] = X[cecha].astype(object).where(X[cecha].notna(), np.nan)
        else:
            X[cecha] = pd.to_numeric(X[cecha]).astype(float)

    # KROK 2. To samo przygotowanie co dla X_test: mediany, skalowanie, kolumny 0/1, średnie gmin.
    X = preprocessing.transform(X)
    x = X[0]

    modele = []
    wyjasnienia = []

    for metryki in opis["modele"]:
        model_name = metryki["nazwa"]
        model = models[model_name]

        # KROK 3. Cena za metr z tego modelu.
        y_pred = model.predict(X)
        if model_name in opis["log_models"]:
            y_pred = np.exp(y_pred)
        cena_modelu = float(y_pred[0])

        modele.append({
            "nazwa": model_name,
            "cenaM2": cena_modelu,
            "mae": metryki["mae"],
            "rmse": metryki["rmse"],
            "r2": metryki["r2"],
        })

        # KROK 4. Ile dołożyła każda kolumna: regresja przez współczynniki, drzewa przez SHAP.
        if hasattr(model, "coef_"):
            srednia = np.array(opis["srednia_dzialka"])
            wklady_kolumn = model.coef_ * (x - srednia)
            start = float(model.intercept_ + model.coef_ @ srednia)
        else:
            wklady_kolumn = objasniacze[model_name].shap_values(X)[0]
            start = float(np.ravel(objasniacze[model_name].expected_value)[0])

        # KROK 5. Kolumny po przygotowaniu wracają do swoich cech, np. "kategorie__nier_prawo_wlasnosc" to "nier_prawo".
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

        # KROK 6. Modele na logarytmie: wkłady przeliczamy na zł/m², żeby dalej sumowały się do ceny.
        if model_name in opis["log_models"]:
            cena_startowa = math.exp(start)
            cena = math.exp(start + sum(sumy.values()))
            mnoznik = cena
            if abs(math.log(cena) - math.log(cena_startowa)) > 1e-12:
                mnoznik = (cena - cena_startowa) / (math.log(cena) - math.log(cena_startowa))
            for cecha in sumy:
                sumy[cecha] = sumy[cecha] * mnoznik
        else:
            cena_startowa = start
            cena = start + sum(sumy.values())

        wklady = []
        for cecha, wartosc in sumy.items():
            wklady.append({"kod": cecha, "wklad": wartosc})
        wklady.sort(key=lambda w: abs(w["wklad"]), reverse=True)

        wyjasnienia.append({"model": model_name, "start": cena_startowa, "cena": cena, "wklady": wklady})

    # KROK 7. Wynik z najlepszego modelu i przedział 80% zależny od liczby sprzedaży w okolicy (0, 1, 10, 30+).
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
