import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingRegressor

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import OneHotEncoder

from sklearn.metrics import mean_absolute_error

import config
from etl.etap6_cechy.sasiedztwo import CECHY as CECHY_SASIEDZTWA
from etl.etap6_cechy.cechy_dzialki import PRZEZNACZENIA


GRUPY = {
    "transakcja": ["tran_sprzedajacy", "nier_prawo", "dzi_sposob_uzyt"],
    "lokalizacja": ["teryt_woj", "teryt_powiat"],
    "polozenie": ["x_2180", "y_2180", "log_powierzchnia", "wskaznik_zwartosci"],
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

dane = pd.read_parquet(config.SCIEZKA_PELNE_CECHY, columns=CECHY + ["cena_m2", "zbior"])
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

print(f"Progi ceny z treningu: {dol:.2f} - {gora:.2f} zł/m2")
print(f"Uczenie: {len(train):,}   test: {len(test):,} (odrzucono {odrzucone:,})   cech: {len(CECHY)}")

y_train = train["cena_m2"].to_numpy()
y_test = test["cena_m2"].to_numpy()

results = {}

for nazwa, co_pominac in config.EKSPERYMENTY.items():
    pominiete = []
    for element in co_pominac:
        if element in GRUPY:
            pominiete += GRUPY[element]
        else:
            pominiete.append(element)

    cechy = [c for c in CECHY if c not in pominiete]
    liczby = [c for c in cechy if c not in KATEGORYCZNE]
    kategorie = [c for c in cechy if c in KATEGORYCZNE]

    preprocessing = ColumnTransformer(
        [
            ("liczby", make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True), StandardScaler()), liczby),
            ("kategorie", make_pipeline(SimpleImputer(strategy="constant", fill_value="brak", keep_empty_features=True), OneHotEncoder(handle_unknown="ignore", sparse_output=False)), kategorie),
        ],
        sparse_threshold=0,
    )
    X_train = preprocessing.fit_transform(train[cechy])
    X_test = preprocessing.transform(test[cechy])

    model = HistGradientBoostingRegressor(
        loss="absolute_error",
        max_iter=600,
        learning_rate=0.08,
        max_leaf_nodes=63,
        min_samples_leaf=40,
        random_state=1,
    )
    model.fit(X_train, np.log(y_train))
    y_pred = np.exp(np.clip(model.predict(X_test), np.log(dol), np.log(gora)))

    results[nazwa] = {
        "cech": len(cechy),
        "mae": mean_absolute_error(y_test, y_pred),
        "mediana_bledu": np.median(np.abs(y_pred - y_test) / y_test) * 100,
    }
    print(f"{nazwa}: MAE {results[nazwa]['mae']:.2f}")

print("\nEksperymenty z cechami (Gradient Boosting):")
print(f"{'Eksperyment':<24} {'Cech':>5} {'MAE':>8} {'Zmiana MAE':>11} {'Mediana błędu':>14}")
for nazwa, wynik in results.items():
    zmiana = wynik["mae"] - results["wszystkie_cechy"]["mae"]
    print(f"{nazwa:<24} {wynik['cech']:>5} {wynik['mae']:>8.2f} {zmiana:>+11.2f} {wynik['mediana_bledu']:>13.1f}%")
