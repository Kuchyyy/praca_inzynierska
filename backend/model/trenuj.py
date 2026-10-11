import json
import shutil
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.base import clone
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import BayesianRidge, LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder
from sklearn.tree import DecisionTreeRegressor

import config
from model.przygotowanie import przygotuj_wejscia

# Drugi element mówi, czy model uczy się na logarytmie ceny. Wybrane na walidacji
# z 2024 roku (WALIDACJA_OD), bez zaglądania do testu: regresje i drzewo wypadły lepiej
# na logarytmie, las na cenie wprost. Boosting przewiduje medianę ceny (absolute_error),
# więc nie zaniża drogich lokalizacji tak jak model na logarytmie.
MODELE = {
    "Linear Regression": (LinearRegression(), True),
    "Bayesian Ridge": (BayesianRidge(), True),
    "Decision Tree": (DecisionTreeRegressor(max_depth=12, min_samples_leaf=20, random_state=1), True),
    "Random Forest": (
        RandomForestRegressor(n_estimators=100, min_samples_leaf=20, max_features=0.5, n_jobs=-1, random_state=1),
        False,
    ),
    "Gradient Boosting": (
        HistGradientBoostingRegressor(
            loss="absolute_error",
            max_iter=600,
            learning_rate=0.08,
            max_leaf_nodes=63,
            min_samples_leaf=40,
            random_state=1,
        ),
        False,
    ),
}

# Powiaty i gminy maja setki i tysiace wartosci. Zamiast tylu kolumn 0/1
# kazda dostaje srednia log-ceny z treningu, liczona krzyzowo, bez przecieku celu.
DUZO_KATEGORII = ["teryt_powiat", "teryt_gmina"]

# Przedzial wyceny zalezy od tego, ile transakcji bylo w okolicy.
KOSZYKI_TRANSAKCJI = [0, 1, 10, 30]


def zbuduj_przetwarzanie(opis):
    male = [n for n in opis["kategoryczne"] if n not in DUZO_KATEGORII]
    duze = [n for n in opis["kategoryczne"] if n in DUZO_KATEGORII]

    liczby = Pipeline([
        ("braki", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
        ("skala", StandardScaler()),
    ])
    kategorie = Pipeline([
        ("braki", SimpleImputer(strategy="constant", fill_value="__BRAK__", keep_empty_features=True)),
        ("kodowanie", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    teryt = Pipeline([
        ("braki", SimpleImputer(strategy="constant", fill_value="__BRAK__", keep_empty_features=True)),
        ("srednie", TargetEncoder(target_type="continuous", cv=KFold(5, shuffle=True, random_state=1))),
    ])
    return ColumnTransformer(
        [
            ("liczby", liczby, opis["liczbowe"]),
            ("kategorie", kategorie, male),
            ("teryt", teryt, duze),
        ],
        remainder="drop",
        sparse_threshold=0,
    )


def zbuduj_potok(opis, model, na_logarytmie):
    potok = Pipeline([
        ("przetwarzanie", zbuduj_przetwarzanie(opis)),
        ("model", clone(model)),
    ])
    # Ceny dzialek roznia sie tysiackrotnie, czesc modeli uczy sie wiec na logarytmie.
    if na_logarytmie:
        potok = TransformedTargetRegressor(regressor=potok, func=np.log, inverse_func=np.exp)
    return potok


def cecha_kolumny(nazwa, opis):
    # Kolumna po przetworzeniu, np. "kategorie__nier_prawo_uzytkowanieWieczyste",
    # wraca do cechy z kontraktu. Wskazniki brakow naleza do swojej cechy.
    nazwa = nazwa.split("__", 1)[1].removeprefix("missingindicator_")
    if nazwa in opis["cechy"]:
        return nazwa
    for cecha in opis["kategoryczne"]:
        if nazwa.startswith(cecha + "_"):
            return cecha
    raise ValueError(f"Nieznana kolumna po przetworzeniu: {nazwa}")


def koszyk(liczba):
    numer = 0
    for i, prog in enumerate(KOSZYKI_TRANSAKCJI):
        if liczba >= prog:
            numer = i
    return numer


def trenuj_modele():
    cel = Path(config.SCIEZKA_MODELU)
    if cel.exists():
        print(f"Korzystam z zapisanych modeli: {cel}")
        return

    cel.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(cel.parent).free < (config.ZAPAS_DYSKU_GIB + 2) * 1024**3:
        raise RuntimeError("Potrzeba 10 GiB zapasu i miejsca na modele")

    poczatek = time.monotonic()
    kontrakt = json.loads((Path(config.SCIEZKA_AUDYT) / "cechy_modelu.json").read_text())
    wariant = config.WARIANT_MODELU
    opis = kontrakt["warianty"][wariant]

    kolumny = list(dict.fromkeys(opis["cechy"] + ["cena_m2", "zbior", "dzi_sposob_uzyt"]))
    wejscie = Path(config.SCIEZKA_PELNE_CECHY) / "transakcje.parquet"
    dane = pq.read_table(wejscie, columns=kolumny).to_pandas()

    uczenie = dane[dane.zbior == "trening"]
    test = dane[dane.zbior == "test"]

    # W RCN zostaly pomylki rzedu milionow zl/m². Progi bierzemy tylko z treningu
    # i tak samo stosujemy je do testu, zeby metryki nie zalezaly od kilku bledow.
    dol = float(uczenie.cena_m2.quantile(config.CENA_M2_KWANTYL_DOL))
    gora = float(uczenie.cena_m2.quantile(config.CENA_M2_KWANTYL_GORA))
    uczenie = uczenie[uczenie.cena_m2.between(dol, gora)]
    test_przed = len(test)
    test = test[test.cena_m2.between(dol, gora)]

    print(f"Progi ceny z treningu: {dol:.2f} - {gora:.2f} zl/m2")
    print(f"Uczenie: {len(uczenie):,}   test: {len(test):,} (odrzucono {test_przed - len(test):,})   cech: {len(opis['cechy'])}")
    print()

    x_ucz = przygotuj_wejscia(uczenie, kontrakt, wariant)
    x_tst = przygotuj_wejscia(test, kontrakt, wariant)
    y_ucz = uczenie.cena_m2.to_numpy()
    y_tst = test.cena_m2.to_numpy()

    wytrenowane = {}
    przewidywania = {}
    metryki = []

    for nazwa, (model, na_logarytmie) in MODELE.items():
        start = time.monotonic()

        potok = zbuduj_potok(opis, model, na_logarytmie)
        potok.fit(x_ucz, y_ucz)
        przewidywane = potok.predict(x_tst)

        mae = mean_absolute_error(y_tst, przewidywane)
        rmse = float(np.sqrt(mean_squared_error(y_tst, przewidywane)))
        r2 = r2_score(y_tst, przewidywane)
        mediana_bledu = float(np.median(np.abs(przewidywane - y_tst) / y_tst))
        czas = time.monotonic() - start
        print(f"{nazwa:<20} MAE: {mae:8.2f}   RMSE: {rmse:8.2f}   R2: {r2:6.3f}   mediana bledu: {mediana_bledu:6.1%}   {czas:5.0f} s")

        wytrenowane[nazwa] = potok
        przewidywania[nazwa] = przewidywane
        metryki.append({
            "nazwa": nazwa,
            "na_logarytmie": na_logarytmie,
            "mae": float(mae),
            "rmse": rmse,
            "r2": float(r2),
            "mediana_bledu_procent": mediana_bledu * 100,
            "czas_sekundy": round(czas, 1),
        })

    najlepszy = min(metryki, key=lambda m: m["mae"])["nazwa"]
    print()
    print(f"Najlepszy model: {najlepszy}")

    # Przedzial 80%: o ile na tescie prawdziwa cena odbiegala od wyceny.
    # Liczony osobno dla okolic z mala i duza liczba transakcji.
    stosunek = y_tst / przewidywania[najlepszy]
    koszyki_testu = np.array([koszyk(n) for n in test.liczba_transakcji_2km_24m.fillna(0)])
    przedzialy = []
    for numer, prog in enumerate(KOSZYKI_TRANSAKCJI):
        maska = koszyki_testu == numer
        przedzialy.append({
            "od_transakcji": prog,
            "dol": float(np.quantile(stosunek[maska], 0.1)),
            "gora": float(np.quantile(stosunek[maska], 0.9)),
            "mae": float(mean_absolute_error(y_tst[maska], przewidywania[najlepszy][maska])),
            "liczba": int(maska.sum()),
        })

    # Blad najlepszego modelu dla kazdego rodzaju gruntu.
    bledy_gruntow = {}
    for rodzaj in sorted(test.dzi_sposob_uzyt.dropna().unique()):
        maska = (test.dzi_sposob_uzyt == rodzaj).to_numpy()
        bledy_gruntow[rodzaj] = {
            "mae": float(mean_absolute_error(y_tst[maska], przewidywania[najlepszy][maska])),
            "liczba": int(maska.sum()),
        }

    # Waznosc globalna: o ile rosnie MAE na probce testu, gdy wartosci cechy sie przetasuje.
    # Ta sama metoda dla kazdego modelu. Sluzy tylko do opisu i niczego nie dobiera.
    probka = np.random.default_rng(1).choice(len(x_tst), size=min(config.WAZNOSC_PROBKA, len(x_tst)), replace=False)
    waznosc = {}
    for nazwa, potok in wytrenowane.items():
        start = time.monotonic()
        wynik = permutation_importance(
            potok,
            x_tst.iloc[probka],
            y_tst[probka],
            scoring="neg_mean_absolute_error",
            n_repeats=config.WAZNOSC_POWTORZENIA,
            random_state=1,
        )
        waznosc[nazwa] = {cecha: float(w) for cecha, w in zip(x_tst.columns, wynik.importances_mean)}
        print(f"Waznosc permutacyjna {nazwa}: {time.monotonic() - start:.0f} s")

    # Regresje wyjasniamy wzgledem sredniej dzialki z treningu: zapisujemy srednie kolumn po przetworzeniu.
    srednie_kolumn = {}
    for nazwa, potok in wytrenowane.items():
        rdzen = potok.regressor_ if isinstance(potok, TransformedTargetRegressor) else potok
        if hasattr(rdzen.named_steps["model"], "coef_"):
            srednie_kolumn[nazwa] = rdzen.named_steps["przetwarzanie"].transform(x_ucz).mean(axis=0).tolist()

    # Statystyki cech z treningu do opisu cech w panelu.
    statystyki = {}
    korelacje = uczenie[opis["liczbowe"]].corrwith(uczenie.cena_m2, method="spearman")
    for cecha in opis["liczbowe"]:
        znane = uczenie[cecha].dropna()
        kwantyle = [None] * 6
        if len(znane):
            kwantyle = [float(k) for k in znane.quantile([0, 0.25, 0.5, 0.75, 0.99, 1])]
        statystyki[cecha] = {
            "min": kwantyle[0],
            "p25": kwantyle[1],
            "mediana": kwantyle[2],
            "p75": kwantyle[3],
            "p99": kwantyle[4],
            "max": kwantyle[5],
            "srednia": float(znane.mean()) if len(znane) else None,
            "zera_procent": float((znane == 0).mean() * 100) if len(znane) else None,
            "braki_procent": float(uczenie[cecha].isna().mean() * 100),
            "spearman": float(korelacje[cecha]) if pd.notna(korelacje[cecha]) else None,
        }
    for cecha in opis["kategoryczne"]:
        grupy = uczenie.groupby(cecha).cena_m2.agg(["size", "median"]).sort_values("size", ascending=False)
        najczestsze = []
        for wartosc, wiersz in grupy.head(5).iterrows():
            najczestsze.append({"wartosc": str(wartosc), "liczba": int(wiersz["size"]), "mediana_ceny": float(wiersz["median"])})
        statystyki[cecha] = {
            "mediana": None,
            "braki_procent": float(uczenie[cecha].isna().mean() * 100),
            "liczba_wartosci": int(uczenie[cecha].nunique()),
            "najczestsze": najczestsze,
        }

    podsumowanie = {
        "wariant": wariant,
        "cechy": opis["cechy"],
        "kategoryczne": opis["kategoryczne"],
        "liczbowe": opis["liczbowe"],
        "najlepszy": najlepszy,
        "modele": metryki,
        "przedzialy": przedzialy,
        "bledy_gruntow": bledy_gruntow,
        "waznosc": waznosc,
        "srednie_kolumn": srednie_kolumn,
        "statystyki": statystyki,
        "progi_ceny": {"dol": dol, "gora": gora},
        "uczenie": {"wiersze": len(uczenie), "przed": config.TEST_OD},
        "test": {"wiersze": len(test), "odrzucone": test_przed - len(test), "od": config.TEST_OD},
        "uwagi": "Progi ceny tylko z treningu. Metryki w zl/m2 na tescie od TEST_OD, na tych samych progach.",
        "czas_sekundy": round(time.monotonic() - poczatek),
    }

    with TemporaryDirectory(prefix=".model-", dir=cel.parent) as katalog:
        roboczy = Path(katalog) / "model"
        roboczy.mkdir()
        joblib.dump(wytrenowane, roboczy / "modele.joblib", compress=3)
        (roboczy / "podsumowanie.json").write_text(json.dumps(podsumowanie, ensure_ascii=False, indent=2))
        roboczy.rename(cel)

    rozmiar = (cel / "modele.joblib").stat().st_size
    print(f"Zapisano: {cel} ({rozmiar / 1024**2:.0f} MiB, {podsumowanie['czas_sekundy']} s)")


if __name__ == "__main__":
    trenuj_modele()
