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
from sklearn.preprocessing import TargetEncoder
from sklearn.model_selection import KFold

from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_squared_error
from sklearn.metrics import r2_score

import config
from etl.sasiedztwo_cenowe.polska import CECHY as CECHY_SASIEDZTWA
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

# Ceny działek różnią się tysiąckrotnie, więc te modele uczą się na logarytmie ceny.
log_models = ["Linear Regression", "Bayesian Ridge", "Decision Tree"]

KOSZYKI_TRANSAKCJI = [0, 1, 10, 30]


def przetwarzanie(cechy):
    liczby = [c for c in cechy if c not in KATEGORYCZNE]
    kategorie = [c for c in cechy if c in KATEGORYCZNE and c not in ["teryt_powiat", "teryt_gmina"]]
    teryt = [c for c in cechy if c in ["teryt_powiat", "teryt_gmina"]]

    liczby_kroki = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        StandardScaler(),
    )
    kategorie_kroki = make_pipeline(
        SimpleImputer(strategy="constant", fill_value="brak", keep_empty_features=True),
        OneHotEncoder(handle_unknown="ignore", sparse_output=False),
    )

    # Powiatów i gmin są setki, więc zamiast kolumn 0/1 dostają średnią log-ceny z treningu.
    teryt_kroki = make_pipeline(
        SimpleImputer(strategy="constant", fill_value="brak", keep_empty_features=True),
        TargetEncoder(target_type="continuous", cv=KFold(5, shuffle=True, random_state=1)),
    )

    return ColumnTransformer(
        [
            ("liczby", liczby_kroki, liczby),
            ("kategorie", kategorie_kroki, kategorie),
            ("teryt", teryt_kroki, teryt),
        ],
        sparse_threshold=0,
    )


dane = pd.read_parquet(config.SCIEZKA_PELNE_CECHY, columns=CECHY + ["cena_m2", "zbior"])
for cecha in KATEGORYCZNE:
    dane[cecha] = dane[cecha].astype(object).where(dane[cecha].notna(), np.nan)

train = dane[dane["zbior"] == "trening"]
test = dane[dane["zbior"] == "test"]

# W RCN zostały pomyłki rzędu milionów zł/m². Progi liczymy tylko na treningu.
dol = float(train["cena_m2"].quantile(config.CENA_M2_KWANTYL_DOL))
gora = float(train["cena_m2"].quantile(config.CENA_M2_KWANTYL_GORA))

train = train[train["cena_m2"].between(dol, gora)]
odrzucone = len(test)
test = test[test["cena_m2"].between(dol, gora)]
odrzucone -= len(test)

print(f"Progi ceny z treningu: {dol:.2f} - {gora:.2f} zł/m2")
print(f"Uczenie: {len(train):,}   test: {len(test):,} (odrzucono {odrzucone:,})   cech: {len(CECHY)}")

y_train = train["cena_m2"].to_numpy()
y_test = test["cena_m2"].to_numpy()

start = time.monotonic()

preprocessing = przetwarzanie(CECHY)
X_train = preprocessing.fit_transform(train[CECHY], np.log(y_train))
X_test = preprocessing.transform(test[CECHY])

results = {}
predictions = {}

for model_name, model in models.items():
    model_start = time.monotonic()

    if model_name in log_models:
        model.fit(X_train, np.log(y_train))
        y_pred = np.exp(model.predict(X_test))
    else:
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

    predictions[model_name] = y_pred
    results[model_name] = {
        "nazwa": model_name,
        "na_logarytmie": model_name in log_models,
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "r2": float(r2_score(y_test, y_pred)),
        "mediana_bledu_procent": float(np.median(np.abs(y_pred - y_test) / y_test) * 100),
        "czas_sekundy": round(time.monotonic() - model_start, 1),
    }

    print(f"{model_name}: {results[model_name]['czas_sekundy']:.0f} s")

print("\nWyniki na teście:")
print(f"{'Model':<20} {'MAE':>8} {'RMSE':>8} {'R2':>7} {'Mediana błędu':>14}")
for model_name, wynik in results.items():
    print(
        f"{model_name:<20} "
        f"{wynik['mae']:>8.2f} "
        f"{wynik['rmse']:>8.2f} "
        f"{wynik['r2']:>7.3f} "
        f"{wynik['mediana_bledu_procent']:>13.1f}%"
    )

best = min(results, key=lambda model_name: results[model_name]["mae"])
print(f"\nNajlepszy model: {best}")

# Przedział 80%: o ile prawdziwa cena na teście odbiegała od wyceny, osobno wg liczby transakcji w okolicy.
stosunek = y_test / predictions[best]
koszyki = np.digitize(test["liczba_transakcji_2km_24m"].fillna(0), KOSZYKI_TRANSAKCJI) - 1

przedzialy = []
for numer, prog in enumerate(KOSZYKI_TRANSAKCJI):
    maska = koszyki == numer
    przedzialy.append({
        "od_transakcji": prog,
        "dol": float(np.quantile(stosunek[maska], 0.1)),
        "gora": float(np.quantile(stosunek[maska], 0.9)),
        "mae": float(mean_absolute_error(y_test[maska], predictions[best][maska])),
        "liczba": int(maska.sum()),
    })

bledy_gruntow = {}
for rodzaj in sorted(test["dzi_sposob_uzyt"].dropna().unique()):
    maska = (test["dzi_sposob_uzyt"] == rodzaj).to_numpy()
    bledy_gruntow[rodzaj] = {
        "mae": float(mean_absolute_error(y_test[maska], predictions[best][maska])),
        "liczba": int(maska.sum()),
    }

statystyki = {}
korelacje = train[LICZBOWE].corrwith(train["cena_m2"], method="spearman")
for cecha in LICZBOWE:
    znane = train[cecha].dropna()
    kwantyle = [float(k) for k in znane.quantile([0, 0.25, 0.5, 0.75, 0.99, 1])]
    statystyki[cecha] = {
        "min": kwantyle[0],
        "p25": kwantyle[1],
        "mediana": kwantyle[2],
        "p75": kwantyle[3],
        "p99": kwantyle[4],
        "max": kwantyle[5],
        "srednia": float(znane.mean()),
        "zera_procent": float((znane == 0).mean() * 100),
        "braki_procent": float(train[cecha].isna().mean() * 100),
        "spearman": float(korelacje[cecha]) if pd.notna(korelacje[cecha]) else None,
    }
for cecha in KATEGORYCZNE:
    grupy = train.groupby(cecha)["cena_m2"].agg(["size", "median"]).sort_values("size", ascending=False)
    najczestsze = []
    for wartosc, wiersz in grupy.head(5).iterrows():
        najczestsze.append({"wartosc": str(wartosc), "liczba": int(wiersz["size"]), "mediana_ceny": float(wiersz["median"])})
    statystyki[cecha] = {
        "mediana": None,
        "braki_procent": float(train[cecha].isna().mean() * 100),
        "liczba_wartosci": int(train[cecha].nunique()),
        "najczestsze": najczestsze,
    }

opis = {
    "cechy": CECHY,
    "kategoryczne": KATEGORYCZNE,
    "liczbowe": LICZBOWE,
    "log_models": log_models,
    "koszyki": KOSZYKI_TRANSAKCJI,
    "najlepszy": best,
    "modele": list(results.values()),
    "przedzialy": przedzialy,
    "bledy_gruntow": bledy_gruntow,
    # Ważność cech dopisuje waznosc_cech.py, uruchamiany po treningu.
    "waznosc": {},
    "statystyki": statystyki,
    "srednia_dzialka": X_train.mean(axis=0).tolist(),
    "progi_ceny": {"dol": dol, "gora": gora},
    "uczenie": {"wiersze": len(train), "przed": config.TEST_OD},
    "test": {"wiersze": len(test), "odrzucone": odrzucone, "od": config.TEST_OD},
}

joblib.dump({"przetwarzanie": preprocessing, "modele": models, "opis": opis}, config.SCIEZKA_MODELU, compress=3)
print(f"Zapisano model: {config.SCIEZKA_MODELU} ({time.monotonic() - start:.0f} s)")
