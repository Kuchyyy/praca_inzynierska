import contextlib
import io
import unittest

import numpy as np
import pandas as pd

from etl.sasiedztwo_cenowe.polska import dodaj_sasiedztwo, CECHY
from etl.wczytanie_i_czyszczenie_cech.pozostale import dodaj_pozostale


def probka():
    return pd.DataFrame(
        {
            "dok_data": pd.to_datetime(
                ["2022-06-01", "2023-06-01", "2024-06-01", "2025-06-01"]
            ),
            "cena_m2": [100.0, 200.0, 300.0, 400.0],
            "dzi_id_dzialki": ["a", "b", "c", "d"],
            "dzi_sposob_uzyt": ["rolny"] * 4,
            "teryt_gmina": ["0201011"] * 4,
            "teryt_obreb": ["020101_1.0001"] * 4,
            "teryt_woj": ["02", "04", "14", "30"],
            "x_2180": [0.0, 100.0, 200.0, 300.0],
            "y_2180": [0.0] * 4,
        }
    )


class PozostaleTest(unittest.TestCase):
    def policz(self, dane):
        with contextlib.redirect_stdout(io.StringIO()):
            return dodaj_sasiedztwo(dane, "2024-01-01")

    def test_wczesniejsze_ceny_treningowe_i_granice_wojewodztw(self):
        wynik = self.policz(probka())
        self.assertTrue(np.isnan(wynik.loc[0, "mediana_cena_m2_gmina"]))
        self.assertEqual(wynik.loc[1, "mediana_cena_m2_2km_24m"], 100)
        self.assertEqual(wynik.loc[2, "mediana_cena_m2_2km_24m"], 150)
        self.assertEqual(wynik.loc[2, "trend_cen_gmina_12m"], 1)
        self.assertEqual(wynik.loc[3, "mediana_cena_m2_2km_24m"], 200)
        self.assertEqual(wynik.loc[3, "odl_najblizsza_transakcja_m"], 200)
        self.assertEqual(wynik.zbior.tolist(), ["trening", "trening", "test", "test"])

    def test_ceny_testowe_nie_zmieniaja_zadnej_cechy(self):
        dane = probka()
        przed = self.policz(dane)
        dane.loc[2:, "cena_m2"] = [999999, 888888]
        po = self.policz(dane)
        pd.testing.assert_frame_equal(przed[CECHY], po[CECHY])

    def test_brak_sasiadow_z_tego_samego_dnia_i_tej_samej_dzialki(self):
        dane = probka()
        dane.loc[1, "dok_data"] = dane.loc[0, "dok_data"]
        dane.loc[2, "dzi_id_dzialki"] = "a"
        wynik = self.policz(dane)
        self.assertTrue(np.isnan(wynik.loc[1, "odl_najblizsza_transakcja_m"]))
        self.assertEqual(wynik.loc[2, "mediana_cena_m2_gmina"], 200)
        self.assertEqual(wynik.loc[2, "liczba_transakcji_2km_24m"], 1)

    def test_daleki_sasiad_i_brak_w_oknie_czasowym(self):
        dane = probka()
        dane.loc[2:, "x_2180"] = 100000
        dane.loc[3, "dok_data"] = pd.Timestamp("2027-01-01")
        wynik = self.policz(dane)
        self.assertEqual(wynik.loc[2, "odl_najblizsza_transakcja_m"], 99900)
        self.assertEqual(wynik.loc[3, "liczba_transakcji_2km_24m"], 0)
        self.assertTrue(np.isnan(wynik.loc[3, "mediana_cena_m2_5km_24m"]))

    def test_przyszla_cena_treningowa_nie_zmienia_przeszlosci(self):
        dane = probka()
        przed = self.policz(dane)
        dane.loc[1, "cena_m2"] = 999999
        po = self.policz(dane)
        pd.testing.assert_frame_equal(przed.loc[:1, CECHY], po.loc[:1, CECHY])

    def test_podstawowe_i_przeznaczenie_nie_udaja_planu(self):
        dane = pd.DataFrame(
            {
                "powierzchnia_m2": [1000.0] * 3,
                "dok_data": pd.to_datetime(["2015-01-01", "2016-02-01", "2025-03-01"]),
                "pole_geom_m2": [1000.0] * 3,
                "obwod_m": [140.0] * 3,
                "dzi_adres": ["MSC: Wroclaw ;UL: Test", None, "MSC:;"],
                "dzi_przezn_wmpzp": [
                    None,
                    "decyzjaWarunkiZabudowy;terenRolniczy",
                    "nowaKategoria",
                ],
            }
        )
        wynik = dodaj_pozostale(dane)
        self.assertEqual(wynik.miesiace_od_2015.tolist(), [0, 13, 122])
        self.assertEqual(wynik.loc[0, "miejscowosc"], "WROCLAW")
        self.assertTrue(pd.isna(wynik.loc[2, "miejscowosc"]))
        self.assertEqual(wynik.przezn_brak_danych.tolist(), [1, 0, 0])
        self.assertEqual(wynik.przezn_nieznana_kategoria.tolist(), [0, 0, 1])
        self.assertEqual(wynik.loc[1, "przezn_decyzjaWarunkiZabudowy"], 1)
        self.assertNotIn("ma_mpzp", wynik.columns)
        np.testing.assert_allclose(wynik.log_powierzchnia, np.log(1000))
        np.testing.assert_allclose(wynik.wskaznik_zwartosci, 4 * np.pi * 1000 / 140**2)
