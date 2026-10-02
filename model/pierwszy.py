import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import BayesianRidge, LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
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

modele = {
    "liniowa": LinearRegression(),
    "bayesowska": BayesianRidge(),
    "drzewo": DecisionTreeRegressor(max_depth=12, min_samples_leaf=20, random_state=1),
    "las": RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        min_samples_leaf=20,
        n_jobs=-1,
        random_state=1,
    ),
}

print("PIERWSZY MODEL")
print("-" * 78)
print(f"Podzial po dacie: test od {prog}")
print(f"Uczenie: {len(uczenie):,}   test: {len(test):,}   cech: {len(kolumny)}")
print("Osobny model na kazdy sposob uzytkowania")
print()

rodzaje = sorted(uczenie["sposob_uzytkowania"].dropna().unique())

for nazwa_modelu in modele:
    print(nazwa_modelu)
    print("-" * 78)

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

        model = modele[nazwa_modelu].__class__(**modele[nazwa_modelu].get_params())
        model.fit(x_ucz, y_ucz)
        przewidywane = model.predict(x_tst)

        blad = mean_absolute_error(y_tst, przewidywane)
        r2 = r2_score(y_tst, przewidywane) if len(tst) > 1 else float("nan")
        mediana_ceny = y_tst.median()
        print(
            f"  {rodzaj:<40} n={len(tst):>5,}   "
            f"mediana {mediana_ceny:7.1f}   "
            f"blad {blad:7.2f} zl/m2   "
            f"R2 {r2:6.3f}"
        )

        wszystkie_prawdziwe.extend(y_tst.tolist())
        wszystkie_przewidywane.extend(przewidywane.tolist())

    if wszystkie_prawdziwe:
        blad = mean_absolute_error(wszystkie_prawdziwe, wszystkie_przewidywane)
        r2 = r2_score(wszystkie_prawdziwe, wszystkie_przewidywane)
        print(f"  {'RAZEM':<40} n={len(wszystkie_prawdziwe):>5,}   "
              f"{'':16}"
              f"blad {blad:7.2f} zl/m2   "
              f"R2 {r2:6.3f}")
    print()
