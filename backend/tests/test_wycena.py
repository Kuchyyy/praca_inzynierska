import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor

from model.eksperyment import grupy_cech, wybierz_cechy
from model.sprawdz_cechy import porownaj
from model.trenuj import cecha_kolumny, koszyk, zbuduj_potok
from wycena.cechy import cechy_formularza
from wycena import model as wycena_model

DZIALKA = {
    "identyfikator": "126102_9.0047.106/2",
    "zrodloGranicy": "uldk",
    "terytObrebu": "126102_9.0047",
    "granica": [],
    "powierzchnia": "3 397,5",
    "rodzajGruntu": "gruntyRolne",
    "przeznaczenie": "budownictwoMieszkanioweJednorodzinne",
    "prawo": "wlasnoscNieruchomosciGruntowej",
    "sprzedajacy": "osobaFizyczna",
    "dataWyceny": "2026-10-09",
}


class FormularzTest(unittest.TestCase):
    def test_teryt_czas_i_przeznaczenie_jak_w_etl(self):
        cechy = cechy_formularza(DZIALKA)
        self.assertEqual(cechy["teryt_woj"], "12")
        self.assertEqual(cechy["teryt_powiat"], "1261")
        self.assertEqual(cechy["teryt_gmina"], "1261029")
        self.assertEqual(cechy["miesiace_od_2015"], 141)
        self.assertEqual(cechy["powierzchnia_m2"], 3397.5)
        self.assertEqual(cechy["przezn_budownictwoMieszkanioweJednorodzinne"], 1)
        self.assertEqual(cechy["przezn_terenRolniczy"], 0)
        self.assertEqual(cechy["ma_wpis_przeznaczenia"], 1)
        self.assertEqual(cechy["przezn_brak_danych"], 0)

    def test_bledny_obreb_i_puste_pole_zatrzymuja_wycene(self):
        with self.assertRaises(ValueError):
            cechy_formularza({**DZIALKA, "terytObrebu": "Kraków"})
        with self.assertRaises(ValueError):
            cechy_formularza({**DZIALKA, "przeznaczenie": ""})
        with self.assertRaises(ValueError):
            cechy_formularza({**DZIALKA, "powierzchnia": "0"})


class ModelTest(unittest.TestCase):
    def test_kolumny_wracaja_do_cech(self):
        opis = {"cechy": ["pole", "nier_prawo"], "kategoryczne": ["nier_prawo"]}
        self.assertEqual(cecha_kolumny("liczby__pole", opis), "pole")
        self.assertEqual(cecha_kolumny("liczby__missingindicator_pole", opis), "pole")
        self.assertEqual(cecha_kolumny("kategorie__nier_prawo_uzytkowanieWieczyste", opis), "nier_prawo")

    def test_koszyk_transakcji(self):
        self.assertEqual([koszyk(n) for n in [0, 1, 9, 10, 29, 30, 500]], [0, 1, 1, 2, 2, 3, 3])

    def test_wklady_kazdego_modelu_sumuja_sie_do_jego_wyceny(self):
        opis = {
            "cechy": ["pole", "odleglosc", "nier_prawo", "teryt_gmina"],
            "liczbowe": ["pole", "odleglosc"],
            "kategoryczne": ["nier_prawo", "teryt_gmina"],
        }
        losowe = np.random.default_rng(1)
        dane = pd.DataFrame({
            "pole": losowe.uniform(100, 5000, 400),
            "odleglosc": np.where(losowe.random(400) < 0.1, np.nan, losowe.uniform(0, 900, 400)),
            "nier_prawo": losowe.choice(["a", "b"], 400),
            "teryt_gmina": losowe.choice(["g1", "g2", "g3"], 400),
        })
        cena = 60 + dane.pole / 100 - dane.odleglosc.fillna(500) / 20 + (dane.nier_prawo == "b") * 30

        # Regresja i drzewo na logarytmie ceny, las i boosting na cenie wprost, jak w MODELE.
        ustawienia = {
            "Linear Regression": (LinearRegression(), True),
            "Decision Tree": (DecisionTreeRegressor(max_depth=4, random_state=1), True),
            "Random Forest": (RandomForestRegressor(n_estimators=10, min_samples_leaf=5, random_state=1), False),
            "Gradient Boosting": (HistGradientBoostingRegressor(loss="absolute_error", max_iter=30, random_state=1), False),
        }
        modele = {}
        metryki = []
        srednie_kolumn = {}
        for nazwa, (model, na_logarytmie) in ustawienia.items():
            potok = zbuduj_potok(opis, model, na_logarytmie)
            potok.fit(dane, cena)
            modele[nazwa] = potok
            metryki.append({"nazwa": nazwa, "na_logarytmie": na_logarytmie})
            if nazwa == "Linear Regression":
                srednie_kolumn[nazwa] = potok.regressor_.named_steps["przetwarzanie"].transform(dane).mean(axis=0).tolist()
        opis = {**opis, "modele": metryki, "srednie_kolumn": srednie_kolumn}

        cechy = {"pole": 1200.0, "odleglosc": None, "nier_prawo": "b", "teryt_gmina": "g2"}
        wycena_model.objasniacz.cache_clear()
        with patch.object(wycena_model, "wczytaj", return_value=(modele, opis)):
            for m in metryki:
                with self.subTest(model=m["nazwa"]):
                    wynik = wycena_model.wyjasnij(cechy, m)
                    oczekiwana = modele[m["nazwa"]].predict(wycena_model.wejscie_modelu(cechy))[0]
                    suma = wynik["start"] + sum(w["wklad"] for w in wynik["wklady"])
                    self.assertAlmostEqual(suma, oczekiwana, places=5)
                    self.assertAlmostEqual(wynik["cena"], oczekiwana, places=5)
                    self.assertEqual({w["kod"] for w in wynik["wklady"]}, set(opis["cechy"]))
        wycena_model.objasniacz.cache_clear()


class SprawdzenieCechTest(unittest.TestCase):
    def test_porownanie_z_tolerancja(self):
        wynik = {"zgodne": 0, "rozne": 0, "brak_w_etl": 0, "brak_w_panelu": 0, "max_roznica": 0.0, "przyklady": []}
        porownaj(wynik, "odl_woda_m", 100.0, 100.3, "a")
        porownaj(wynik, "odl_woda_m", 100.0, 101.0, "b")
        porownaj(wynik, "liczba_budynkow_250m", 5, 5, "c")
        porownaj(wynik, "teryt_gmina", "1261029", "1261029", "d")
        porownaj(wynik, "mediana_cena_m2_gmina", None, None, "e")
        porownaj(wynik, "mediana_cena_m2_gmina", None, 3.0, "f")

        self.assertEqual(wynik["zgodne"], 4)
        self.assertEqual(wynik["rozne"], 1)
        self.assertEqual(wynik["brak_w_etl"], 1)
        self.assertEqual(wynik["przyklady"][0]["klucz"], "b")
        self.assertAlmostEqual(wynik["max_roznica"], 1.0)


class EksperymentTest(unittest.TestCase):
    OPIS = {
        "cechy": ["tran_sprzedajacy", "teryt_gmina", "powierzchnia_m2", "rok", "odl_woda_m",
                  "przezn_las", "ma_wpis_przeznaczenia", "mediana_cena_m2_gmina"],
        "liczbowe": ["powierzchnia_m2", "rok", "odl_woda_m", "przezn_las", "ma_wpis_przeznaczenia", "mediana_cena_m2_gmina"],
        "kategoryczne": ["tran_sprzedajacy", "teryt_gmina"],
    }

    def test_grupy_obejmuja_kazda_ceche_raz(self):
        grupy = grupy_cech(self.OPIS["cechy"])
        wszystkie = [c for lista in grupy.values() for c in lista]
        self.assertEqual(sorted(wszystkie), sorted(self.OPIS["cechy"]))
        self.assertEqual(grupy["osm"], ["odl_woda_m"])
        self.assertEqual(grupy["przeznaczenie"], ["przezn_las", "ma_wpis_przeznaczenia"])

    def test_pominiecie_grupy_i_lista_cech(self):
        bez = wybierz_cechy(self.OPIS, pomin_grupy=["sasiedztwo", "lokalizacja"])
        self.assertNotIn("mediana_cena_m2_gmina", bez["cechy"])
        self.assertEqual(bez["kategoryczne"], ["tran_sprzedajacy"])
        self.assertEqual(bez["pominiete"], ["mediana_cena_m2_gmina", "teryt_gmina"])

        tylko = wybierz_cechy(self.OPIS, tylko_cechy=["rok", "teryt_gmina"])
        self.assertEqual(tylko["cechy"], ["teryt_gmina", "rok"])
        self.assertEqual(tylko["liczbowe"], ["rok"])

        with self.assertRaises(ValueError):
            wybierz_cechy(self.OPIS, pomin_grupy=["nie_ma_takiej"])


if __name__ == "__main__":
    unittest.main()
