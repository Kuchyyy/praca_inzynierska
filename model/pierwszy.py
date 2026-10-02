import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import BayesianRidge, LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.tree import DecisionTreeRegressor


dane = pd.read_parquet("db/dane/gotowe/dane_z_cechami.parquet")
dane = dane.dropna(subset=["cena_m2", "data_transakcji", "sposob_uzytkowania"])
dane = dane.sort_values("data_transakcji")

prog = dane["data_transakcji"].quantile(0.8)
uczenie = dane[dane["data_transakcji"] < prog]
test = dane[dane["data_transakcji"] >= prog]

pomin = {
    "cena_m2",
    "cena_brutto",
    "data_transakcji",
    "id_transakcji",
    "dzi_id_dzialki",
    "geometry",
    "miejscowosc",
    "sposob_uzytkowania",
    "prawo",
    "sprzedajacy",
    "zrodlo_powierzchni",
    "dzi_przezn_wmpzp",
}

kolumny = []
for nazwa in dane.columns:
    if nazwa in pomin:
        continue
    if pd.api.types.is_numeric_dtype(dane[nazwa]):
        kolumny.append(nazwa)

models = [
    LinearRegression(),
    BayesianRidge(),
    DecisionTreeRegressor(max_depth=12, min_samples_leaf=20, random_state=1),
    RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        min_samples_leaf=20,
        n_jobs=-1,
        random_state=1,
    ),
]

model_names = [
    "Linear Regression",
    "Bayesian Ridge",
    "Decision Tree",
    "Random Forest",
]

print(f"Podzial po dacie: test od {prog}")
print(f"Uczenie: {len(uczenie):,}   test: {len(test):,}   cech: {len(kolumny)}")
print("Osobny model na kazdy sposob uzytkowania")
print()

rodzaje = sorted(uczenie["sposob_uzytkowania"].dropna().unique())

wyniki_mae = np.zeros(len(models))
wyniki_rmse = np.zeros(len(models))
wyniki_r2 = np.zeros(len(models))
wyniki_n = np.zeros(len(models), dtype=int)

for j, model in enumerate(models):
    print(f"=== {model_names[j]} ===")

    wszystkie_prawdziwe = []
    wszystkie_przewidywane = []

    for rodzaj in rodzaje:
        ucz = uczenie[uczenie["sposob_uzytkowania"] == rodzaj]
        tst = test[test["sposob_uzytkowania"] == rodzaj]

        if len(ucz) < 50 or len(tst) == 0:
            print(f"  {rodzaj:<40} za malo danych")
            continue

        mediany = ucz[kolumny].median()
        x_ucz = ucz[kolumny].fillna(mediany)
        x_tst = tst[kolumny].fillna(mediany)
        y_ucz = ucz["cena_m2"]
        y_tst = tst["cena_m2"]

        model_fit = clone(model)
        model_fit.fit(x_ucz, y_ucz)
        przewidywane = model_fit.predict(x_tst)

        mae = mean_absolute_error(y_tst, przewidywane)
        rmse = np.sqrt(mean_squared_error(y_tst, przewidywane))
        r2 = r2_score(y_tst, przewidywane) if len(tst) > 1 else float("nan")
        print(
            f"  {rodzaj:<40} n={len(tst):>5,}   "
            f"MAE: {mae:7.2f}   "
            f"RMSE: {rmse:7.2f}   "
            f"R2: {r2:6.3f}"
        )

        wszystkie_prawdziwe.extend(y_tst.tolist())
        wszystkie_przewidywane.extend(przewidywane.tolist())

    if wszystkie_prawdziwe:
        y_true = np.array(wszystkie_prawdziwe)
        y_pred = np.array(wszystkie_przewidywane)
        wyniki_mae[j] = mean_absolute_error(y_true, y_pred)
        wyniki_rmse[j] = np.sqrt(mean_squared_error(y_true, y_pred))
        wyniki_r2[j] = r2_score(y_true, y_pred)
        wyniki_n[j] = len(y_true)
        print(
            f"  {'RAZEM':<40} n={wyniki_n[j]:>5,}   "
            f"MAE: {wyniki_mae[j]:7.2f}   "
            f"RMSE: {wyniki_rmse[j]:7.2f}   "
            f"R2: {wyniki_r2[j]:6.3f}"
        )
    print()

print("=== Ranking modeli po MAE ===")
kolejnosc = np.argsort(wyniki_mae)
for i in kolejnosc:
    if wyniki_n[i] == 0:
        continue
    print(
        f"{model_names[i]} | "
        f"MAE: {wyniki_mae[i]:.3f} | "
        f"RMSE: {wyniki_rmse[i]:.3f} | "
        f"R2: {wyniki_r2[i]:.3f}"
    )
