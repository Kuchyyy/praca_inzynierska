import time

import joblib
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

from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_squared_error
from sklearn.metrics import r2_score

import config
from etl.etap6_cechy.sasiedztwo import CECHY as CECHY_SASIEDZTWA
from etl.etap6_cechy.cechy_dzialki import PRZEZNACZENIA


TRANSAKCJA = ["tran_sprzedajacy", "nier_prawo", "dzi_sposob_uzyt"]
LOKALIZACJA = ["teryt_woj", "teryt_powiat"]
POLOZENIE = ["x_2180", "y_2180", "log_powierzchnia", "wskaznik_zwartosci"]
CZAS = ["rok", "miesiace_od_2015"]
OSM = [
    "odl_najblizszy_budynek_m",
    "liczba_budynkow_1000m",
    "odl_droga_dowolna_m",
    "odl_droga_utwardzona_m",
    "liczba_poi_1km",
    "udzial_lasu_500m",
    "odl_miasto_pow_50k_m",
]
PRZEZNACZENIE = ["przezn_" + nazwa for nazwa in PRZEZNACZENIA] + ["przezn_brak_danych", "ma_wpis_przeznaczenia"]
SASIEDZTWO = CECHY_SASIEDZTWA

CECHY = TRANSAKCJA + LOKALIZACJA + POLOZENIE + CZAS + OSM + PRZEZNACZENIE + SASIEDZTWO

KATEGORYCZNE = TRANSAKCJA + LOKALIZACJA
LICZBOWE = [cecha for cecha in CECHY if cecha not in KATEGORYCZNE]

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


KOSZYKI_TRANSAKCJI = [0, 1, 10, 30]


def przetwarzanie(cechy):
    liczby = [c for c in cechy if c not in KATEGORYCZNE]
    kategorie = [c for c in cechy if c in KATEGORYCZNE]

    liczby_kroki = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        StandardScaler(),
    )
    kategorie_kroki = make_pipeline(
        SimpleImputer(strategy="constant", fill_value="brak", keep_empty_features=True),
        OneHotEncoder(handle_unknown="ignore", sparse_output=False),
    )

    return ColumnTransformer(
        [
            ("liczby", liczby_kroki, liczby),
            ("kategorie", kategorie_kroki, kategorie),
        ],
        sparse_threshold=0,
    )


dane = pd.read_parquet(config.SCIEZKA_PELNE_CECHY, columns=CECHY + ["cena_m2", "zbior", "dok_data"])
for cecha in KATEGORYCZNE:
    dane[cecha] = dane[cecha].astype(object).where(dane[cecha].notna(), np.nan)

train = dane[dane["zbior"] == "trening"]
test = dane[dane["zbior"] == "test"]

dol = float(train["cena_m2"].quantile(config.CENA_M2_KWANTYL_DOL))
gora = float(train["cena_m2"].quantile(config.CENA_M2_KWANTYL_GORA))

train = train[train["cena_m2"].between(dol, gora)]
odrzucone = len(test)
test = test[test["cena_m2"].between(dol, gora)]
odrzucone -= len(test)

log_dol = np.log(dol)
log_gora = np.log(gora)

print(f"Progi ceny z treningu: {dol:.2f} - {gora:.2f} zł/m2")
print(f"Trening: {len(train):,}   test: {len(test):,} (odrzucono {odrzucone:,})   cech: {len(CECHY)}")

start = time.monotonic()


print(f"\nKrok 1: wybór modelu i przedziału 80% na walidacji (od {config.WALIDACJA_OD})")
uczenie = train[train["dok_data"] < config.WALIDACJA_OD]
walidacja = train[train["dok_data"] >= config.WALIDACJA_OD]
print(f"Uczenie: {len(uczenie):,}   walidacja: {len(walidacja):,}")

y_uczenie = uczenie["cena_m2"].to_numpy()
y_walidacja = walidacja["cena_m2"].to_numpy()

preprocessing = przetwarzanie(CECHY)
X_uczenie = preprocessing.fit_transform(uczenie[CECHY])
X_walidacja = preprocessing.transform(walidacja[CECHY])

mae_walidacja = {}
predictions_walidacja = {}

for model_name, model in models.items():
    model.fit(X_uczenie, np.log(y_uczenie))
    y_pred = np.exp(np.clip(model.predict(X_walidacja), log_dol, log_gora))

    predictions_walidacja[model_name] = y_pred
    mae_walidacja[model_name] = float(mean_absolute_error(y_walidacja, y_pred))
    print(f"{model_name}: MAE na walidacji {mae_walidacja[model_name]:.2f}")

best = min(mae_walidacja, key=lambda model_name: mae_walidacja[model_name])
print(f"Najlepszy model na walidacji: {best}")

stosunek = y_walidacja / predictions_walidacja[best]
koszyki = np.digitize(walidacja["liczba_transakcji_2km_24m"].fillna(0), KOSZYKI_TRANSAKCJI) - 1

przedzialy = []
for numer, prog in enumerate(KOSZYKI_TRANSAKCJI):
    maska = koszyki == numer
    przedzialy.append({
        "od_transakcji": prog,
        "dol": float(np.quantile(stosunek[maska], 0.1)),
        "gora": float(np.quantile(stosunek[maska], 0.9)),
        "mae": float(mean_absolute_error(y_walidacja[maska], predictions_walidacja[best][maska])),
        "liczba": int(maska.sum()),
    })


print(f"\nKrok 2: końcowe modele uczone na całym treningu (przed {config.TEST_OD}), ocena na teście")
y_train = train["cena_m2"].to_numpy()
y_test = test["cena_m2"].to_numpy()

preprocessing = przetwarzanie(CECHY)
X_train = preprocessing.fit_transform(train[CECHY])
X_test = preprocessing.transform(test[CECHY])

results = {}
predictions = {}

for model_name, model in models.items():
    model_start = time.monotonic()

    model.fit(X_train, np.log(y_train))
    y_pred = np.exp(np.clip(model.predict(X_test), log_dol, log_gora))

    predictions[model_name] = y_pred
    results[model_name] = {
        "nazwa": model_name,
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "r2": float(r2_score(y_test, y_pred)),
        "mediana_bledu_procent": float(np.median(np.abs(y_pred - y_test) / y_test) * 100),
        "czas_sekundy": round(time.monotonic() - model_start, 1),
    }

    print(f"{model_name}: {results[model_name]['czas_sekundy']:.0f} s")

print("\nWyniki (MAE wal. = walidacja 2024, reszta = test):")
print(f"{'Model':<20} {'MAE wal.':>9} {'MAE':>8} {'RMSE':>8} {'R2':>7} {'Mediana błędu':>14}")
for model_name, wynik in results.items():
    print(
        f"{model_name:<20} "
        f"{mae_walidacja[model_name]:>9.2f} "
        f"{wynik['mae']:>8.2f} "
        f"{wynik['rmse']:>8.2f} "
        f"{wynik['r2']:>7.3f} "
        f"{wynik['mediana_bledu_procent']:>13.1f}%"
    )

print(f"\nWycenę w panelu daje model wybrany na walidacji: {best}")

stosunek = y_test / predictions[best]
koszyki = np.digitize(test["liczba_transakcji_2km_24m"].fillna(0), KOSZYKI_TRANSAKCJI) - 1
w_przedziale = np.zeros(len(y_test), dtype=bool)

print("\nPokrycie przedziału 80% na teście:")
print(f"{'Transakcji w 2 km':<18} {'Przedział':>14} {'Pokrycie':>9} {'Liczba':>8}")
for numer, przedzial in enumerate(przedzialy):
    maska = koszyki == numer
    w_przedziale[maska] = (stosunek[maska] >= przedzial["dol"]) & (stosunek[maska] <= przedzial["gora"])
    przedzial["pokrycie_test"] = float(w_przedziale[maska].mean() * 100)
    print(
        f"{str(przedzial['od_transakcji']) + '+':<18} "
        f"{przedzial['dol']:>6.2f} - {przedzial['gora']:<5.2f} "
        f"{przedzial['pokrycie_test']:>8.1f}% "
        f"{int(maska.sum()):>8,}"
    )
print(f"{'wszystkie':<18} {'':>14} {w_przedziale.mean() * 100:>8.1f}% {len(y_test):>8,}")

statystyki = {}
for cecha in LICZBOWE:
    znane = train[cecha].dropna()
    statystyki[cecha] = {
        "min": float(znane.min()),
        "mediana": float(znane.median()),
        "max": float(znane.max()),
        "srednia": float(znane.mean()),
    }

opis = {
    "cechy": CECHY,
    "kategoryczne": KATEGORYCZNE,
    "liczbowe": LICZBOWE,
    "koszyki": KOSZYKI_TRANSAKCJI,
    "najlepszy": best,
    "modele": list(results.values()),
    "przedzialy": przedzialy,
    "waznosc": {},
    "statystyki": statystyki,
    "srednia_dzialka": X_train.mean(axis=0).tolist(),
    "progi_ceny": {"dol": dol, "gora": gora},
    "uczenie": {"wiersze": len(train), "przed": config.TEST_OD},
    "walidacja": {"wiersze": len(walidacja), "od": config.WALIDACJA_OD, "mae": mae_walidacja},
    "test": {"wiersze": len(test), "odrzucone": odrzucone, "od": config.TEST_OD},
}

joblib.dump({"przetwarzanie": preprocessing, "modele": models, "opis": opis}, config.SCIEZKA_MODELU, compress=3)
print(f"Zapisano model: {config.SCIEZKA_MODELU} ({time.monotonic() - start:.0f} s)")
