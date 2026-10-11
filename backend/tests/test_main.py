import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config


class MainTest(unittest.TestCase):
    def test_etapy_wykonuja_sie_po_kolei(self):
        with tempfile.TemporaryDirectory() as katalog:
            root = Path(katalog)
            kolejnosc = []

            with (
                patch.multiple(
                    config,
                    SCIEZKA_OCZYSZCZONE=str(root / "oczyszczone"),
                    SCIEZKA_PO_ULDK=str(root / "po_uldk"),
                    UZUPELNIJ_ULDK=True,
                    TRENUJ_MODELE=True,
                ),
                patch(
                    "etl.wczytanie_i_czyszczenie_cech.wczytywanie.oczysc_plik",
                    side_effect=lambda **ustawienia: kolejnosc.append("czyszczenie"),
                ),
                patch(
                    "etl.uldk.uzupelnij.pobierz_brakujace_granice",
                    side_effect=lambda: kolejnosc.append("granice") or {"proba": True},
                ),
                patch(
                    "etl.uldk.uzupelnij.przelicz_po_uldk",
                    side_effect=lambda opis: kolejnosc.append("przeliczenie"),
                ),
                patch("etl.audyt_danych.audytuj_dane", side_effect=lambda: kolejnosc.append("audyt")),
                patch("etl.walidacja_modelu.przygotuj_dane_walidacyjne", side_effect=lambda: kolejnosc.append("walidacja")),
                patch("model.trenuj.trenuj_modele", side_effect=lambda: kolejnosc.append("trening")),
                patch("builtins.print"),
            ):
                runpy.run_path("main.py", run_name="__main__")

            self.assertEqual(kolejnosc, ["czyszczenie", "granice", "przeliczenie", "audyt", "walidacja", "trening"])

    def test_zapisany_wynik_i_wylaczone_pobieranie(self):
        with tempfile.TemporaryDirectory() as katalog:
            with (
                patch.multiple(config, SCIEZKA_OCZYSZCZONE=katalog, UZUPELNIJ_ULDK=False),
                patch("etl.wczytanie_i_czyszczenie_cech.wczytywanie.oczysc_plik") as czysc,
                patch("etl.uldk.uzupelnij.pobierz_brakujace_granice") as pobierz,
                patch("etl.uldk.uzupelnij.przelicz_po_uldk") as przelicz,
                patch("etl.audyt_danych.audytuj_dane"),
                patch("etl.walidacja_modelu.przygotuj_dane_walidacyjne"),
                patch("builtins.print"),
            ):
                runpy.run_path("main.py", run_name="__main__")

                czysc.assert_not_called()
                pobierz.assert_not_called()
                przelicz.assert_not_called()
