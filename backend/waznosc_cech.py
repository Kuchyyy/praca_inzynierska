import joblib
import numpy as np
import pandas as pd

from sklearn.metrics import mean_absolute_error

import config


# Ważność cechy: o ile rośnie MAE, gdy przetasujemy jej wartości między działkami.
# Liczona na wytrenowanych modelach z model.joblib, wynik dopisywany do tego samego pliku (panel go pokazuje).
zapis = joblib.load(config.SCIEZKA_MODELU)
preprocessing = zapis["przetwarzanie"]
models = zapis["modele"]
opis = zapis["opis"]

CECHY = opis["cechy"]
KATEGORYCZNE = opis["kategoryczne"]
log_models = opis["log_models"]

dane = pd.read_parquet(config.SCIEZKA_PELNE_CECHY, columns=CECHY + ["cena_m2", "zbior"])
for cecha in KATEGORYCZNE:
    dane[cecha] = dane[cecha].astype(object).where(dane[cecha].notna(), np.nan)

# Ten sam test co w modele.py: progi ceny z treningu zapisane w opisie modelu.
test = dane[dane["zbior"] == "test"]
test = test[test["cena_m2"].between(opis["progi_ceny"]["dol"], opis["progi_ceny"]["gora"])]

sample = test.sample(min(config.WAZNOSC_PROBKA, len(test)), random_state=1)
X_sample = sample[CECHY]
y_sample = sample["cena_m2"].to_numpy()
print(f"Ważność cech: {len(sample):,} transakcji z testu, {config.WAZNOSC_POWTORZENIA} przetasowania każdej z {len(CECHY)} cech")

base_mae = {}
waznosc = {}
for model_name, model in models.items():
    y_pred = model.predict(preprocessing.transform(X_sample))
    if model_name in log_models:
        y_pred = np.exp(y_pred)
    base_mae[model_name] = mean_absolute_error(y_sample, y_pred)
    waznosc[model_name] = dict.fromkeys(CECHY, 0.0)

rng = np.random.default_rng(1)
for cecha in CECHY:
    for powtorzenie in range(config.WAZNOSC_POWTORZENIA):
        X_shuffled = X_sample.copy()
        X_shuffled[cecha] = rng.permutation(X_shuffled[cecha].to_numpy())
        X_shuffled = preprocessing.transform(X_shuffled)

        for model_name, model in models.items():
            y_pred = model.predict(X_shuffled)
            if model_name in log_models:
                y_pred = np.exp(y_pred)
            wzrost = mean_absolute_error(y_sample, y_pred) - base_mae[model_name]
            waznosc[model_name][cecha] += wzrost / config.WAZNOSC_POWTORZENIA

najlepszy = opis["najlepszy"]
print(f"\nNajważniejsze cechy ({najlepszy}), wzrost MAE po przetasowaniu [zł/m²]:")
ranking = sorted(waznosc[najlepszy].items(), key=lambda para: para[1], reverse=True)
for miejsce, (cecha, wzrost) in enumerate(ranking[:15], 1):
    print(f"{miejsce:>3}. {cecha:<38} {wzrost:>7.2f}")

opis["waznosc"] = waznosc
joblib.dump(zapis, config.SCIEZKA_MODELU, compress=3)
print(f"\nZapisano ważność w {config.SCIEZKA_MODELU}")
