import time

import numpy as np
import pandas as pd

from sklearn.linear_model import LinearRegression
from sklearn.linear_model import BayesianRidge
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.ensemble import HistGradientBoostingRegressor

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import OneHotEncoder
from sklearn.preprocessing import TargetEncoder
from sklearn.model_selection import KFold

from sklearn.metrics import mean_absolute_error

import config
from etl.sasiedztwo_cenowe.polska import CECHY as CECHY_SASIEDZTWA
from etl.sasiedztwo_cenowe.polska import dodaj_sasiedztwo
from etl.wczytanie_i_czyszczenie_cech.pozostale import PRZEZNACZENIA


GRUPY = {
    "transakcja": ["tran_sprzedajacy", "nier_prawo", "dzi_sposob_uzyt"],
    "lokalizacja": ["teryt_woj", "teryt_powiat", "teryt_gmina"],
    "polozenie": ["x_2180", "y_2180", "powierzchnia_m2", "log_powierzchnia", "wskaznik_zwartosci"],
    "czas": ["rok", "miesiace_od_2015"],
    "osm": [
        "odl_najblizszy_budynek_m",
        "liczba_budynkow_1000m",
        "odl_droga_dowolna_m",
        "odl_droga_utwardzona_m",
        "liczba_poi_1km",
        "udzial_lasu_500m",
        "odl_miasto_pow_50k_m",
    ],
    "przeznaczenie": ["przezn_" + nazwa for nazwa in PRZEZNACZENIA] + ["przezn_brak_danych", "ma_wpis_przeznaczenia"],
    "sasiedztwo": CECHY_SASIEDZTWA,
}

CECHY = []
for lista in GRUPY.values():
    CECHY += lista

KATEGORYCZNE = GRUPY["transakcja"] + GRUPY["lokalizacja"]

models = {
    "Linear Regression": LinearRegression(),
    "Bayesian Ridge": BayesianRidge(),
    "Decision Tree": DecisionTreeRegressor(max_depth=12, min_samples_leaf=20, random_state=1),
    "Random Forest": RandomForestRegressor(n_estimators=100, min_samples_leaf=20, max_features=0.5, n_jobs=-1, random_state=1),
    "Gradient Boosting": HistGradientBoostingRegressor(
        loss="absolute_error",
        max_iter=600,
        learning_rate=0.08,
        max_leaf_nodes=63,
        min_samples_leaf=40,
        random_state=1,
    ),
}

log_models = ["Linear Regression", "Bayesian Ridge", "Decision Tree"]


def przetwarzanie(cechy):
    liczby = [c for c in cechy if c not in KATEGORYCZNE]
    kategorie = [c for c in cechy if c in KATEGORYCZNE and c not in ["teryt_powiat", "teryt_gmina"]]
    teryt = [c for c in cechy if c in ["teryt_powiat", "teryt_gmina"]]

    return ColumnTransformer(
        [
            ("liczby", make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True), StandardScaler()), liczby),
            ("kategorie", make_pipeline(SimpleImputer(strategy="constant", fill_value="brak", keep_empty_features=True), OneHotEncoder(handle_unknown="ignore", sparse_output=False)), kategorie),
            ("teryt", make_pipeline(SimpleImputer(strategy="constant", fill_value="brak", keep_empty_features=True), TargetEncoder(target_type="continuous", cv=KFold(5, shuffle=True, random_state=1))), teryt),
        ],
        sparse_threshold=0,
    )


kolumny = list(dict.fromkeys(CECHY + ["cena_m2", "dok_data", "dzi_id_dzialki", "teryt_obreb"]))
wszystkie = pd.read_parquet(config.SCIEZKA_PELNE_CECHY, columns=kolumny)

results = {model_name: [] for model_name in models}
mediany_bledu = {model_name: [] for model_name in models}

for rok in config.WALIDACJA_LATA:
    start = time.monotonic()
    od = pd.Timestamp(f"{rok}-01-01")
    do = pd.Timestamp(f"{rok + 1}-01-01")

    # Cechy sąsiedztwa liczone od nowa: referencją są tylko transakcje sprzed roku walidacji.
    dane = wszystkie[wszystkie["dok_data"] < do].drop(columns=CECHY_SASIEDZTWA)
    dane = dodaj_sasiedztwo(dane, od)
    for cecha in KATEGORYCZNE:
        dane[cecha] = dane[cecha].astype(object).where(dane[cecha].notna(), np.nan)

    train = dane[dane["zbior"] == "trening"]
    valid = dane[dane["zbior"] == "test"]

    # Progi ceny jak w modele.py, liczone tylko na części uczącej.
    dol = float(train["cena_m2"].quantile(config.CENA_M2_KWANTYL_DOL))
    gora = float(train["cena_m2"].quantile(config.CENA_M2_KWANTYL_GORA))
    train = train[train["cena_m2"].between(dol, gora)]
    valid = valid[valid["cena_m2"].between(dol, gora)]

    y_train = train["cena_m2"].to_numpy()
    y_valid = valid["cena_m2"].to_numpy()

    preprocessing = przetwarzanie(CECHY)
    X_train = preprocessing.fit_transform(train[CECHY], np.log(y_train))
    X_valid = preprocessing.transform(valid[CECHY])

    for model_name, model in models.items():
        if model_name in log_models:
            model.fit(X_train, np.log(y_train))
            y_pred = np.exp(model.predict(X_valid))
        else:
            model.fit(X_train, y_train)
            y_pred = model.predict(X_valid)

        results[model_name].append(mean_absolute_error(y_valid, y_pred))
        mediany_bledu[model_name].append(np.median(np.abs(y_pred - y_valid) / y_valid) * 100)

    print(f"Rok {rok}: uczenie {len(train):,}, walidacja {len(valid):,}, {time.monotonic() - start:.0f} s", flush=True)

lata = config.WALIDACJA_LATA
print("\nWalidacja krocząca - MAE [zł/m²]:")
print(f"{'Model':<20} " + " ".join(f"{rok:>8}" for rok in lata) + f" {'średnia':>9} {'odch.':>7}")
for model_name, mae in results.items():
    print(f"{model_name:<20} " + " ".join(f"{m:>8.2f}" for m in mae) + f" {np.mean(mae):>9.2f} {np.std(mae):>7.2f}")

print("\nWalidacja krocząca - mediana błędu [%]:")
print(f"{'Model':<20} " + " ".join(f"{rok:>8}" for rok in lata) + f" {'średnia':>9}")
for model_name, mediana in mediany_bledu.items():
    print(f"{model_name:<20} " + " ".join(f"{m:>7.1f}%" for m in mediana) + f" {np.mean(mediana):>8.1f}%")
