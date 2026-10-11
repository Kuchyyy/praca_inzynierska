import csv
import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import joblib
import numpy as np
import pyarrow.parquet as pq
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

import config
from etl.sasiedztwo_cenowe.polska import CECHY as CECHY_SASIEDZTWA
from model.przygotowanie import przygotuj_wejscia
from model.trenuj import MODELE, zbuduj_potok

# Grupy cech jak w opisie cech w panelu. OSM to wszystko, czego nie ma w pozostałych.
GRUPY_STALE = {
    "transakcja": ["tran_sprzedajacy", "nier_prawo", "dzi_sposob_uzyt"],
    "lokalizacja": ["teryt_woj", "teryt_powiat", "teryt_gmina"],
    "polozenie": ["x_2180", "y_2180", "powierzchnia_m2", "log_powierzchnia", "wskaznik_zwartosci"],
    "czas": ["rok", "miesiace_od_2015"],
}

KOLUMNY_POROWNANIA = [
    "data", "nazwa", "model", "liczba_cech", "pominiete", "mae", "rmse", "r2",
    "mediana_bledu_procent", "roznica_mae_do_wszystkich", "czas_sekundy",
]


def grupy_cech(cechy):
    grupy = {"sasiedztwo": [c for c in cechy if c in CECHY_SASIEDZTWA]}
    for nazwa, lista in GRUPY_STALE.items():
        grupy[nazwa] = [c for c in cechy if c in lista]
    grupy["przeznaczenie"] = [c for c in cechy if c.startswith("przezn_") or c == "ma_wpis_przeznaczenia"]
    znane = {c for lista in grupy.values() for c in lista}
    grupy["osm"] = [c for c in cechy if c not in znane]
    return grupy


def wybierz_cechy(opis, pomin_grupy=(), pomin_cechy=(), tylko_cechy=None):
    # Opis wejść modelu ograniczony do wybranych cech, w kolejności z kontraktu.
    grupy = grupy_cech(opis["cechy"])
    if tylko_cechy:
        wybrane = [c for c in opis["cechy"] if c in set(tylko_cechy)]
        pominiete = [c for c in opis["cechy"] if c not in wybrane]
    else:
        pominiete = list(pomin_cechy)
        for grupa in pomin_grupy:
            if grupa not in grupy:
                raise ValueError(f"Nieznana grupa {grupa}. Dostępne: {', '.join(grupy)}")
            pominiete += grupy[grupa]
        wybrane = [c for c in opis["cechy"] if c not in set(pominiete)]

    if not wybrane:
        raise ValueError("Eksperyment musi mieć choć jedną cechę")
    return {
        "cechy": wybrane,
        "liczbowe": [c for c in opis["liczbowe"] if c in wybrane],
        "kategoryczne": [c for c in opis["kategoryczne"] if c in wybrane],
        "pominiete": sorted(set(pominiete) & set(opis["cechy"])),
    }


def wczytaj_dane(opis):
    # Cechy sąsiedztwa przeliczone z odcięciem WALIDACJA_OD (audyt_modelu/walidacja),
    # żeby ceny z walidacji nie trafiły do cech żadnej transakcji.
    kolumny = ["klucz_transakcji", "cena_m2"] + [c for c in opis["cechy"] if c not in CECHY_SASIEDZTWA]
    dane = pq.read_table(Path(config.SCIEZKA_PELNE_CECHY) / "transakcje.parquet", columns=kolumny).to_pandas()
    sasiedztwo = pq.read_table(Path(config.SCIEZKA_AUDYT) / "walidacja" / "sasiedztwo.parquet").to_pandas()
    dane = dane.merge(sasiedztwo, on="klucz_transakcji", validate="one_to_one")

    uczenie = dane[dane.zbior == "trening"]
    walidacja = dane[dane.zbior == "walidacja"]

    # Progi ceny jak w głównym treningu, ale liczone tylko na części uczącej eksperymentu.
    dol = float(uczenie.cena_m2.quantile(config.CENA_M2_KWANTYL_DOL))
    gora = float(uczenie.cena_m2.quantile(config.CENA_M2_KWANTYL_GORA))
    uczenie = uczenie[uczenie.cena_m2.between(dol, gora)]
    walidacja = walidacja[walidacja.cena_m2.between(dol, gora)]
    print(f"Eksperymenty: uczenie {len(uczenie):,}, walidacja {len(walidacja):,}, progi {dol:.2f}-{gora:.2f} zl/m2", flush=True)
    return uczenie, walidacja


def przeprowadz(nazwa, wybor, uczenie, walidacja):
    katalog = Path(config.SCIEZKA_EKSPERYMENTOW)
    cel = katalog / nazwa
    if cel.exists():
        opis = json.loads((cel / "opis.json").read_text())
        print(f"{nazwa}: korzystam z zapisanego wyniku", flush=True)
        return opis

    katalog.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(katalog).free < (config.ZAPAS_DYSKU_GIB + 1) * 1024**3:
        raise RuntimeError("Potrzeba 10 GiB zapasu na dysku")

    kontrakt = {"warianty": {"eksperyment": wybor}}
    x_ucz = przygotuj_wejscia(uczenie, kontrakt, "eksperyment")
    x_wal = przygotuj_wejscia(walidacja, kontrakt, "eksperyment")
    y_ucz = uczenie.cena_m2.to_numpy()
    y_wal = walidacja.cena_m2.to_numpy()

    # Wynik z wszystkimi cechami, jeśli już jest, służy za punkt odniesienia.
    odniesienie = {}
    plik_wszystkich = katalog / "wszystkie" / "opis.json"
    if plik_wszystkich.exists() and nazwa != "wszystkie":
        for m in json.loads(plik_wszystkich.read_text())["modele"]:
            odniesienie[m["nazwa"]] = m["mae"]

    wytrenowane = {}
    metryki = []
    for nazwa_modelu in config.EKSPERYMENT_MODELE:
        model, na_logarytmie = MODELE[nazwa_modelu]
        start = time.monotonic()
        potok = zbuduj_potok(wybor, model, na_logarytmie)
        potok.fit(x_ucz, y_ucz)
        przewidywane = potok.predict(x_wal)

        mae = float(mean_absolute_error(y_wal, przewidywane))
        wynik = {
            "nazwa": nazwa_modelu,
            "na_logarytmie": na_logarytmie,
            "mae": mae,
            "rmse": float(np.sqrt(mean_squared_error(y_wal, przewidywane))),
            "r2": float(r2_score(y_wal, przewidywane)),
            "mediana_bledu_procent": float(np.median(np.abs(przewidywane - y_wal) / y_wal) * 100),
            "roznica_mae_do_wszystkich": mae - odniesienie[nazwa_modelu] if nazwa_modelu in odniesienie else None,
            "czas_sekundy": round(time.monotonic() - start, 1),
        }
        roznica = wynik["roznica_mae_do_wszystkich"]
        opis_roznicy = f"   zmiana MAE {roznica:+.2f}" if roznica is not None else ""
        print(f"{nazwa}: {nazwa_modelu:<18} MAE {mae:7.2f}   R2 {wynik['r2']:6.3f}   cech {len(wybor['cechy'])}{opis_roznicy}", flush=True)
        wytrenowane[nazwa_modelu] = potok
        metryki.append(wynik)

    opis = {
        "nazwa": nazwa,
        "cechy": wybor["cechy"],
        "liczbowe": wybor["liczbowe"],
        "kategoryczne": wybor["kategoryczne"],
        "pominiete": wybor["pominiete"],
        "modele": metryki,
        "uczenie": {"wiersze": len(uczenie), "przed": config.WALIDACJA_OD},
        "walidacja": {"wiersze": len(walidacja), "od": config.WALIDACJA_OD, "przed": config.TEST_OD},
        "data": datetime.now().isoformat(timespec="seconds"),
    }
    with TemporaryDirectory(prefix=".eksperyment-", dir=katalog) as roboczy:
        wynik_katalog = Path(roboczy) / nazwa
        wynik_katalog.mkdir()
        joblib.dump(wytrenowane, wynik_katalog / "modele.joblib", compress=3)
        (wynik_katalog / "opis.json").write_text(json.dumps(opis, ensure_ascii=False, indent=2))
        wynik_katalog.rename(cel)

    # Jedna linia na model w tabeli porównawczej wszystkich eksperymentów.
    plik = katalog / "porownanie.csv"
    nowy = not plik.exists()
    with plik.open("a", newline="") as wyjscie:
        zapis = csv.DictWriter(wyjscie, fieldnames=KOLUMNY_POROWNANIA)
        if nowy:
            zapis.writeheader()
        for m in metryki:
            zapis.writerow({
                "data": opis["data"],
                "nazwa": nazwa,
                "model": m["nazwa"],
                "liczba_cech": len(wybor["cechy"]),
                "pominiete": " ".join(wybor["pominiete"]),
                "mae": round(m["mae"], 3),
                "rmse": round(m["rmse"], 3),
                "r2": round(m["r2"], 4),
                "mediana_bledu_procent": round(m["mediana_bledu_procent"], 2),
                "roznica_mae_do_wszystkich": "" if m["roznica_mae_do_wszystkich"] is None else round(m["roznica_mae_do_wszystkich"], 3),
                "czas_sekundy": m["czas_sekundy"],
            })
    return opis


def ranking_cech(opis_wszystkich, walidacja):
    # Kolejność cech od najważniejszej: ważność permutacyjna pierwszego modelu na próbce walidacji.
    plik = Path(config.SCIEZKA_EKSPERYMENTOW) / "ranking_cech.json"
    if plik.exists():
        return json.loads(plik.read_text())

    modele = joblib.load(Path(config.SCIEZKA_EKSPERYMENTOW) / "wszystkie" / "modele.joblib")
    nazwa_modelu = config.EKSPERYMENT_MODELE[0]
    kontrakt = {"warianty": {"eksperyment": opis_wszystkich}}
    probka = walidacja.sample(min(config.WAZNOSC_PROBKA, len(walidacja)), random_state=1)
    x = przygotuj_wejscia(probka, kontrakt, "eksperyment")
    wynik = permutation_importance(
        modele[nazwa_modelu], x, probka.cena_m2.to_numpy(),
        scoring="neg_mean_absolute_error", n_repeats=config.WAZNOSC_POWTORZENIA, random_state=1,
    )
    kolejnosc = [x.columns[i] for i in np.argsort(-wynik.importances_mean)]
    plik.write_text(json.dumps(kolejnosc, ensure_ascii=False, indent=2))
    return kolejnosc


def eksperyment():
    kontrakt = json.loads((Path(config.SCIEZKA_AUDYT) / "cechy_modelu.json").read_text())
    opis = kontrakt["warianty"][config.WARIANT_MODELU]
    uczenie, walidacja = wczytaj_dane(opis)

    if config.EKSPERYMENT_SERIA is None:
        wybor = wybierz_cechy(opis, config.EKSPERYMENT_POMIN_GRUPY, config.EKSPERYMENT_POMIN_CECHY, config.EKSPERYMENT_TYLKO_CECHY)
        przeprowadz(config.EKSPERYMENT_NAZWA, wybor, uczenie, walidacja)

    elif config.EKSPERYMENT_SERIA == "grupy":
        przeprowadz("wszystkie", wybierz_cechy(opis), uczenie, walidacja)
        for grupa in grupy_cech(opis["cechy"]):
            przeprowadz(f"bez_{grupa}", wybierz_cechy(opis, pomin_grupy=[grupa]), uczenie, walidacja)

    elif config.EKSPERYMENT_SERIA == "liczba_cech":
        wszystkie = przeprowadz("wszystkie", wybierz_cechy(opis), uczenie, walidacja)
        kolejnosc = ranking_cech(wszystkie, walidacja)
        print("Najważniejsze cechy:", ", ".join(kolejnosc[:10]), flush=True)
        for liczba in config.EKSPERYMENT_LICZBY_CECH:
            przeprowadz(f"top_{liczba}", wybierz_cechy(opis, tylko_cechy=kolejnosc[:liczba]), uczenie, walidacja)

    else:
        raise ValueError(f"Nieznana seria eksperymentów: {config.EKSPERYMENT_SERIA}")

    # Podsumowanie wszystkich dotychczasowych eksperymentów, od najmniejszego błędu.
    plik = Path(config.SCIEZKA_EKSPERYMENTOW) / "porownanie.csv"
    with plik.open() as wejscie:
        wiersze = sorted(csv.DictReader(wejscie), key=lambda w: float(w["mae"]))
    print()
    print(f"{'eksperyment':<22} {'model':<18} {'cech':>5} {'MAE':>8} {'R2':>7} {'zmiana MAE':>11}")
    for w in wiersze:
        zmiana = f"{float(w['roznica_mae_do_wszystkich']):+.2f}" if w["roznica_mae_do_wszystkich"] else ""
        print(f"{w['nazwa']:<22} {w['model']:<18} {w['liczba_cech']:>5} {float(w['mae']):8.2f} {float(w['r2']):7.3f} {zmiana:>11}")
    print(f"Tabela: {plik}")


if __name__ == "__main__":
    eksperyment()
