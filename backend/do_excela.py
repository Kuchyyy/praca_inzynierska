# Proba do Excela. ILE_WIERSZY = None zapisuje caly zbior.

import pandas as pd

import config

ILE_WIERSZY = 2000

KOLUMNY = [
    "data_transakcji",
    "teryt_gmina",
    "miejscowosc",
    "dzi_id_dzialki",
    "powierzchnia_m2",
    "pole_geom_m2",
    "zrodlo_powierzchni",
    "cena_brutto",
    "cena_m2",
    "sposob_uzytkowania",
    "dzi_przezn_wmpzp",
    "ma_mpzp",
    "prawo",
    "sprzedajacy",
    "x_2180",
    "y_2180",
    "wskaznik_zwartosci",
]

df = pd.read_parquet(f"{config.SCIEZKA_GOTOWE}/dane_z_cechami.parquet")

if ILE_WIERSZY is None:
    proba = df
    nazwa_pliku = "wszystko_do_excela.csv"
else:
    proba = df.sample(min(ILE_WIERSZY, len(df)), random_state=42)
    nazwa_pliku = "probka_do_excela.csv"

proba = proba[KOLUMNY].sort_values("data_transakcji")

sciezka = f"{config.SCIEZKA_GOTOWE}/{nazwa_pliku}"

# Srednik i przecinek dziesietny, zeby otworzyc w polskim Excelu.
proba.to_csv(sciezka, index=False, sep=";", decimal=",", encoding="utf-8-sig")

print(f"Zapisano {len(proba):,} transakcji do {sciezka}")
print("Plik otworzysz dwuklikiem w Excelu.")
