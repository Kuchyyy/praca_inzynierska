import contextlib
import io
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock
from http.client import IncompleteRead

from shapely import wkb
from shapely.geometry import box

from etl.uldk.granice import granica_z_odpowiedzi, otworz_cache, znajdz_granice, pobierz_granice


class ULDKTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.baza = otworz_cache(Path(self.tmp.name) / "granice.sqlite")
        self.addCleanup(self.baza.close)
        self.geom = box(350000, 350000, 350025, 350040)

    def test_odpowiedz_zawiera_granice_i_wlasciwy_id_oraz_crs(self):
        tekst = "0\n020101_1.0001.1|SRID=2180;" + self.geom.wkt
        geometria, status = granica_z_odpowiedzi(tekst, "020101_1.0001.1")
        self.assertEqual(status, "ok")
        self.assertEqual(wkb.loads(geometria).area, 1000)
        self.assertEqual(granica_z_odpowiedzi(tekst, "inna")[1], "bledny_id_odpowiedzi")
        self.assertEqual(
            granica_z_odpowiedzi(tekst.replace("2180", "4326"), "020101_1.0001.1")[1],
            "bledny_crs",
        )
        self.assertEqual(
            granica_z_odpowiedzi("0\n020101_1.0001.1|POINT(1 2)", "020101_1.0001.1")[1],
            "bledna_geometria",
        )
        self.assertEqual(granica_z_odpowiedzi("-1 brak wyniku", "a")[1], "brak_wyniku")
        self.assertEqual(
            granica_z_odpowiedzi("<html>blad</html>", "a")[1], "bledna_odpowiedz"
        )

    def test_limit_wspolny_dla_partii_i_wznowienie_z_zapisanych_granic(self):
        stan = {"pozostalo": 1, "zapytania": 0, "pobrane": 0}
        with contextlib.redirect_stdout(io.StringIO()), patch(
            "etl.uldk.granice.time.sleep"
        ), patch(
            "etl.uldk.granice.pobierz_granice", return_value=(self.geom.wkb, "ok")
        ) as pobierz:
            a = znajdz_granice(["a", "a", "b"], self.baza, stan)
            b = znajdz_granice(["a", "b"], self.baza, stan)
        self.assertEqual(pobierz.call_count, 1)
        self.assertEqual(set(a), {"a"})
        self.assertEqual(set(b), {"a"})
        self.assertEqual(stan["pobrane"], 1)
        with patch("etl.uldk.granice.pobierz_granice") as pobierz:
            wynik = znajdz_granice(
                ["a"], self.baza, {"pozostalo": 1, "zapytania": 0, "pobrane": 0}
            )
            pobierz.assert_not_called()
        self.assertEqual(wkb.loads(wynik["a"][0]).area, 1000)
        self.assertIsNotNone(datetime.fromisoformat(wynik["a"][1]).tzinfo)

    def test_blad_uslugi_nie_staje_sie_trwalym_brakiem_dzialki(self):
        stan = {"pozostalo": 3, "zapytania": 0, "pobrane": 0}
        with contextlib.redirect_stdout(io.StringIO()), patch(
            "etl.uldk.granice.time.sleep"
        ), patch(
            "etl.uldk.granice.pobierz_granice", return_value=(None, "blad_sieci")
        ) as pobierz:
            self.assertEqual(znajdz_granice(["a"], self.baza, stan), {})
            self.assertEqual(znajdz_granice(["a"], self.baza, stan), {})
            self.assertEqual(pobierz.call_count, 1)
        wczoraj = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        with self.baza:
            self.baza.execute("UPDATE granice SET pobrano_utc = ?", (wczoraj,))
        with contextlib.redirect_stdout(io.StringIO()), patch(
            "etl.uldk.granice.time.sleep"
        ), patch(
            "etl.uldk.granice.pobierz_granice", return_value=(self.geom.wkb, "ok")
        ) as pobierz:
            self.assertEqual(set(znajdz_granice(["a"], self.baza, stan)), {"a"})
            pobierz.assert_called_once()

    def test_urwana_odpowiedz_nie_przerywa_pobierania(self):
        odpowiedz = MagicMock()
        odpowiedz.headers = {}
        odpowiedz.read.side_effect = IncompleteRead(b"urwane", 100)

        with patch("etl.uldk.granice.urlopen") as otworz:
            otworz.return_value.__enter__.return_value = odpowiedz
            self.assertEqual(pobierz_granice("a"), (None, "blad_sieci"))

    def test_ogromna_odpowiedz_nie_jest_wczytywana(self):
        odpowiedz = MagicMock()
        odpowiedz.headers = {"Content-Length": "4294967296"}

        with patch("etl.uldk.granice.urlopen") as otworz:
            otworz.return_value.__enter__.return_value = odpowiedz
            self.assertEqual(pobierz_granice("a"), (None, "za_duza_odpowiedz"))
            odpowiedz.read.assert_not_called()

    def test_limit_odczytu_bez_naglowka_i_niepelna_tresc(self):
        odpowiedz = MagicMock()
        odpowiedz.headers = {}
        odpowiedz.read.return_value = b"x" * (5 * 1024 * 1024 + 1)

        with patch("etl.uldk.granice.urlopen") as otworz:
            otworz.return_value.__enter__.return_value = odpowiedz
            self.assertEqual(pobierz_granice("a"), (None, "za_duza_odpowiedz"))
            odpowiedz.read.assert_called_once_with(5 * 1024 * 1024 + 1)

            odpowiedz.headers = {"Content-Length": "100"}
            odpowiedz.read.return_value = b"0"
            self.assertEqual(pobierz_granice("a"), (None, "blad_sieci"))

    def test_zero_limitu_nie_odpytuje_sieci(self):
        with patch("etl.uldk.granice.pobierz_granice") as pobierz:
            self.assertEqual(znajdz_granice(["a"], self.baza, {"pozostalo": 0}), {})
            pobierz.assert_not_called()

    def test_brak_miejsca_wstrzymuje_kolejne_zapytanie(self):
        with patch("etl.uldk.granice.shutil.disk_usage") as disk, patch(
            "etl.uldk.granice.pobierz_granice"
        ) as pobierz:
            disk.return_value.free = 1
            with self.assertRaisesRegex(RuntimeError, "miejsca"):
                znajdz_granice(["a"], self.baza, {"pozostalo": 1})
            pobierz.assert_not_called()


if __name__ == "__main__":
    unittest.main()
