import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from etl.sasiedztwo_cenowe.polska import dodaj_sasiedztwo


def przygotuj_wejscia(dane, kontrakt, wariant='mapa'):
    opis = kontrakt['warianty'][wariant]
    # Brak calej kolumny to blad integracji; brak wartosci jest dozwolony.
    brakujace = set(opis['cechy']) - set(dane.columns)
    if brakujace:
        raise ValueError(f'Brak kolumn wejscia: {sorted(brakujace)}')
    wynik = dane[opis['cechy']].copy()
    for nazwa in opis['liczbowe']:
        wynik[nazwa] = pd.to_numeric(wynik[nazwa], errors='raise').astype(float)
        if np.isinf(wynik[nazwa]).any():
            raise ValueError(f'Nieskonczona wartosc: {nazwa}')
    for nazwa in opis['kategoryczne']:
        wynik[nazwa] = wynik[nazwa].map(lambda x: str(x) if pd.notna(x) else np.nan)
    return wynik


def zbuduj_przetwarzanie(kontrakt, wariant='mapa'):
    opis = kontrakt['warianty'][wariant]
    liczby = Pipeline([
        ('braki', SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)),
        ('skala', StandardScaler()),
    ])
    kategorie = Pipeline([
        ('braki', SimpleImputer(strategy='constant', fill_value='__BRAK__', keep_empty_features=True)),
        ('kodowanie', OneHotEncoder(handle_unknown='ignore')),
    ])
    # Ten obiekt nalezy umiescic w Pipeline razem z modelem i zapisac po fit.
    return ColumnTransformer([
        ('liczby', liczby, opis['liczbowe']),
        ('kategorie', kategorie, opis['kategoryczne']),
    ], remainder='drop')


def przygotuj_walidacje(dane, walidacja_od, test_od, pokaz_postep=None):
    if pd.Timestamp(walidacja_od) >= pd.Timestamp(test_od):
        raise ValueError('Walidacja musi poprzedzac test koncowy')
    # Odcinamy test przed jakimikolwiek obliczeniami i przeliczamy referencje.
    rozwoj = dane.loc[dane.dok_data.lt(pd.Timestamp(test_od))].copy()
    maska = rozwoj.dok_data.lt(pd.Timestamp(walidacja_od))
    if not maska.any() or maska.all():
        raise ValueError('Pusty trening lub walidacja')
    rozwoj = dodaj_sasiedztwo(rozwoj, walidacja_od, pokaz_postep)
    rozwoj['zbior'] = rozwoj['zbior'].replace({'test': 'walidacja'})
    return rozwoj
