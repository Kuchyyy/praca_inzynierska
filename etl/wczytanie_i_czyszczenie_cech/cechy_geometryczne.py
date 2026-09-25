import numpy as np


def dodaj_zwartosc(df):
    # 1.0 dla kola, blisko 0 dla waskiego paska.
    df["wskaznik_zwartosci"] = (4 * np.pi * df["pole_geom_m2"]) / (df["obwod_m"] ** 2)

    return df


def dodaj_cechy_geometryczne(df):
    print()
    print("CECHY GEOMETRYCZNE")
    print("-" * 78)

    df = dodaj_zwartosc(df)

    # Wspolrzedne i pole sa juz z modulu geometria.
    ma_wspolrzedne = df["x_2180"].notna().sum()
    print(f"  wspolrzedne srodka dzialki: {ma_wspolrzedne:,} ({100 * ma_wspolrzedne / len(df):.1f}%)")

    zwarte = df["wskaznik_zwartosci"].dropna()
    print(f"  wskaznik zwartosci - mediana: {zwarte.median():.3f}")
    print(f"  dzialek bardzo waskich (ponizej 0.2): {(zwarte < 0.2).sum():,}")

    return df
