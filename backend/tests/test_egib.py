import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import io
import zipfile
import contextlib

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from etl.egib.paczki import wybierz_granice, pobierz_paczke
from etl.uldk.granice import otworz_cache
from etl.wczytanie_i_czyszczenie_cech.geometria import dodaj_geometrie


class EGIBTest(unittest.TestCase):
    def test_wybor_po_id_i_sprzeczne_granice(self):
        with tempfile.TemporaryDirectory() as katalog:
            plik = Path(katalog) / 'paczka.gpkg'
            gpd.GeoDataFrame({
                'id_dzialki': ['a', 'a', 'b', 'b', 'c'],
                'czas_pozyskania': ['2026-10-02'] * 5,
            }, geometry=[box(0, 0, 10, 10), box(0, 0, 10, 10), box(0, 0, 20, 20),
                         box(0, 0, 30, 30), box(0, 0, 1, 1)], crs=2180).to_file(plik, layer='dzialki')
            wynik, sprzeczne = wybierz_granice(plik, {'a', 'b'})
            self.assertEqual(set(wynik), {'a'})
            self.assertEqual(wynik['a'][2], 100)
            self.assertEqual(sprzeczne, 1)

    def test_timeout_jest_ponawiany_i_czesciowy_plik_nie_jest_doklejany(self):
        paczka = io.BytesIO()
        with zipfile.ZipFile(paczka, "w") as archiwum:
            archiwum.writestr("proba.gpkg", b"test")
        tresc = paczka.getvalue()
        odpowiedz = MagicMock()
        odpowiedz.headers = {"Content-Length": str(len(tresc))}
        odpowiedz.read.side_effect = [tresc, b""]
        odpowiedz.__enter__.return_value = odpowiedz

        with tempfile.TemporaryDirectory() as katalog:
            root = Path(katalog)
            (root / "0201.gpkg.zip.part").write_bytes(b"stary fragment")
            with patch("etl.egib.paczki.urlopen", side_effect=[TimeoutError("test"), odpowiedz]) as siec, patch("etl.egib.paczki.time.sleep"), contextlib.redirect_stdout(io.StringIO()):
                plik, gpkg, _, _ = pobierz_paczke("0201", root)
            self.assertEqual(siec.call_count, 2)
            self.assertEqual(plik.read_bytes(), tresc)
            self.assertEqual(gpkg.read_bytes(), b"test")

    def test_trzy_nieudane_proby_koncza_pobieranie_paczki(self):
        with tempfile.TemporaryDirectory() as katalog:
            with patch("etl.egib.paczki.urlopen", side_effect=TimeoutError("test")) as siec, patch("etl.egib.paczki.time.sleep"), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(TimeoutError):
                    pobierz_paczke("0201", Path(katalog))
            self.assertEqual(siec.call_count, 3)

    def test_zly_crs(self):
        with tempfile.TemporaryDirectory() as katalog:
            plik = Path(katalog) / 'paczka.gpkg'
            gpd.GeoDataFrame({'id_dzialki':['a'], 'czas_pozyskania':['2026']},
                            geometry=[box(0,0,1,1)], crs=4326).to_file(plik, layer='dzialki')
            with self.assertRaisesRegex(ValueError, '2180'):
                wybierz_granice(plik, {'a'})

    def test_zrodlo_egib_nie_udaje_uldk_i_rcn_ma_pierwszenstwo(self):
        with tempfile.TemporaryDirectory() as katalog:
            baza = otworz_cache(Path(katalog) / 'cache.sqlite')
            geometria = box(350000,350000,350025,350040).wkb
            with baza:
                baza.execute('INSERT INTO granice_egib VALUES (?,?,?,?,?,?)',
                             ('a', geometria, '2026-10-04', '0201', '2026-10-02', 1000))
            dane = pd.DataFrame({'dzi_id_dzialki':['a','a'], 'geometry':[None,geometria], 'dzi_pow_ewid':[0.1,0.1]})
            with patch('etl.uldk.granice.pobierz_granice') as siec:
                wynik = dodaj_geometrie(dane, pd.DataFrame(), baza, {'pozostalo':1})
                siec.assert_not_called()
            self.assertEqual(wynik.zrodlo_geometrii.tolist(), ['egib','rcn'])
            self.assertTrue(wynik.uldk_pobrano_utc.isna().all())
            self.assertEqual(wynik.loc[0,'egib_pobrano_utc'], '2026-10-04')
            self.assertEqual(wynik.loc[0,'powierzchnia_m2'], 1000)
            baza.close()
