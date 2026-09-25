import os

import pandas as pd

import config
from etl.wczytanie_i_czyszczenie_cech import raport


def wczytaj_dane():
    print("WCZYTYWANIE")
    print("-" * 78)
    print(f"Plik: {config.SCIEZKA_SUROWE}")

    df = pd.read_parquet(config.SCIEZKA_SUROWE, columns=config.KOLUMNY_POTRZEBNE)

    print(f"Wierszy: {len(df):,}")
    print(f"Kolumn:  {len(df.columns)}")

    daty = df["dok_data"].dropna()
    print(f"Daty od {daty.min()} do {daty.max()}")

    ma_geometrie = df["geometry"].notna().sum()
    print(f"Geometria wypelniona w {ma_geometrie:,} wierszach ({100 * ma_geometrie / len(df):.1f}%)")

    raport.powiaty_w_surowych = set(df["teryt"].dropna().unique())
    print(f"Powiatow w pliku: {len(raport.powiaty_w_surowych)}")

    sciezka = os.path.join(config.SCIEZKA_POSREDNIE, "01_wczytane.parquet")
    df.to_parquet(sciezka, index=False)
    print(f"Kopia zapisana do {sciezka}")

    return df
