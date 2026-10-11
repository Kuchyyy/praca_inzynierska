import contextlib
import io
import unittest

import numpy as np
import pandas as pd

from etl.audyt_danych import dostepnosc_cech, profil_kolumny
from model.przygotowanie import przygotuj_wejscia, przygotuj_walidacje, zbuduj_przetwarzanie


class AudytTest(unittest.TestCase):
    def test_mapa_nie_wymaga_danych_sprzedazy(self):
        manifest = {'cechy': ['tran_sprzedajacy', 'dzi_sposob_uzyt', 'nier_prawo',
                              'przezn_las', 'ma_wpis_przeznaczenia', 'miejscowosc',
                              'mediana_cena_m2_2km_ten_sam_uzytek', 'powierzchnia_m2']}
        wynik = dostepnosc_cech(manifest)
        self.assertEqual([p['cecha'] for p in wynik if p['wariant_mapa']], ['powierzchnia_m2'])

    def test_profil_oddziela_test_i_trening(self):
        wynik = profil_kolumny(pd.Series([1., 1., 999., np.nan]), pd.Series([True, True, False, False]))
        self.assertEqual(wynik['trening']['rozne'], 1)
        self.assertEqual(wynik['trening']['kwantyle']['1'], 1.)
        self.assertEqual(wynik['test']['braki'], 1)

    def test_imputacja_nie_uczy_sie_na_tescie(self):
        opis = {'cechy': ['pole', 'typ'], 'liczbowe': ['pole'], 'kategoryczne': ['typ']}
        kontrakt = {'warianty': {'mapa': opis}}
        ucz = pd.DataFrame({'pole': [10., 20., np.nan], 'typ': ['a', None, 'a']})
        tst = pd.DataFrame({'pole': [np.nan, 100000.], 'typ': ['nowa', None]})
        przetwarzanie = zbuduj_przetwarzanie(kontrakt)
        przetwarzanie.fit(przygotuj_wejscia(ucz, kontrakt))
        wynik = przetwarzanie.transform(przygotuj_wejscia(tst, kontrakt))
        self.assertEqual(wynik.shape[0], 2)
        imputer = przetwarzanie.named_transformers_['liczby'].named_steps['braki']
        self.assertEqual(imputer.statistics_[0], 15.)
        with self.assertRaises(ValueError):
            przygotuj_wejscia(tst.drop(columns='typ'), kontrakt)

    def test_walidacja_nie_uzywa_cen_walidacyjnych_ani_testu(self):
        dane = pd.DataFrame({
            'dok_data': pd.to_datetime(['2022-01-01', '2023-01-01', '2024-01-01', '2024-06-01', '2025-01-01']),
            'cena_m2': [10., 20., 9999., 8888., 7777.],
            'dzi_id_dzialki': list('abcde'), 'dzi_sposob_uzyt': ['r'] * 5,
            'teryt_gmina': ['g'] * 5, 'teryt_obreb': ['o'] * 5,
            'x_2180': [0.] * 5, 'y_2180': [0.] * 5,
        })
        with contextlib.redirect_stdout(io.StringIO()):
            wynik = przygotuj_walidacje(dane, '2024-01-01', '2025-01-01')
        self.assertEqual(len(wynik), 4)
        self.assertEqual(wynik.loc[3, 'mediana_cena_m2_gmina'], 15.)
        self.assertEqual(wynik.zbior.tolist(), ['trening', 'trening', 'walidacja', 'walidacja'])

    def test_audyt_pliku_i_uniewaznienie_cache_po_zmianie_danych(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import config
        from etl.audyt_danych import audytuj_dane
        from etl.walidacja_modelu import przygotuj_dane_walidacyjne

        with tempfile.TemporaryDirectory() as katalog:
            root = Path(katalog)
            dane = pd.DataFrame({
                'klucz_transakcji': ['a', 'b', 'c'], 'dzi_id_dzialki': ['a', 'b', 'c'],
                'dok_data': pd.to_datetime(['2023-01-01', '2024-01-01', '2025-01-01']),
                'zbior': ['trening', 'trening', 'test'], 'cena_m2': [1., 2., 3.],
                'powierzchnia_m2': [1000.] * 3, 'udzial_sprzedany': [1.] * 3,
                'do_modelu': [True] * 3, 'teryt_woj': ['02'] * 3,
                'x_2180': [400000.] * 3, 'y_2180': [400000.] * 3,
                'tran_cena_brutto': [1000., 2000., 3000.],
                'dzi_sposob_uzyt': ['r'] * 3, 'teryt_gmina': ['g'] * 3,
                'teryt_obreb': ['o'] * 3,
            })
            dane.to_parquet(root / 'transakcje.parquet')
            manifest = {'cechy': ['powierzchnia_m2', 'teryt_woj'], 'kategoryczne': ['teryt_woj'], 'test_od': '2025-01-01'}
            (root / 'cechy_modelu.json').write_text(json.dumps(manifest))
            with patch.multiple(config, SCIEZKA_PELNE_CECHY=str(root), SCIEZKA_AUDYT=str(root / 'audyt'), ZAPAS_DYSKU_GIB=0), contextlib.redirect_stdout(io.StringIO()):
                raport = audytuj_dane()
                self.assertEqual(raport['status'], 'OK')
                self.assertEqual(audytuj_dane()['sha256'], raport['sha256'])
                walidacja = przygotuj_dane_walidacyjne()
                self.assertEqual(walidacja['podzial'], {'trening': 1, 'walidacja': 1})
                self.assertEqual(przygotuj_dane_walidacyjne(), walidacja)
                zapis = pd.read_parquet(root / 'audyt' / 'walidacja' / 'sasiedztwo.parquet')
                self.assertEqual(zapis.klucz_transakcji.tolist(), ['a', 'b'])
                self.assertEqual(zapis.loc[1, 'mediana_cena_m2_gmina'], 1.)
                dane.loc[2, 'cena_m2'] = -1.
                dane.to_parquet(root / 'transakcje.parquet')
                with self.assertRaises(ValueError):
                    przygotuj_dane_walidacyjne()
                with self.assertRaises(ValueError):
                    audytuj_dane()
                blad = json.loads((root / 'audyt' / 'podsumowanie.json').read_text())
                self.assertEqual(blad['status'], 'BLAD')
                self.assertNotEqual(blad['sha256'], raport['sha256'])
