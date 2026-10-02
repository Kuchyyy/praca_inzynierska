import contextlib
import io
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import CRS
from shapely.geometry import Polygon, box

import config
from etl.wczytanie_i_czyszczenie_cech.wczytywanie import oczysc_plik


DATA_DO = date(2026, 10, 2)


def transakcja(identyfikator, **zmiany):
    wiersz = dict.fromkeys(config.KOLUMNY_POTRZEBNE)
    wiersz.update({
        'teryt': '0201', 'serwis_rcn': 'https://test.invalid/rcn',
        'tran_przestrzen_nazw': 'powiat-a', 'tran_lokalny_id_iip': identyfikator,
        'tran_wersja_id': '2025-01-01T00:00:00', 'tran_cena_brutto': 100000.0,
        'tran_rodzaj_trans': 'wolnyRynek', 'dok_data': datetime(2020, 6, 1),
        'nier_rodzaj': 'nieruchomoscGruntowaNiezabudowana', 'nier_udzial': '1/1',
        'nier_prawo': 'wlasnoscNieruchomosciGruntowej',
        'dzi_id_dzialki': '020101_1.0001.5/2', 'dzi_pow_ewid': 0.1,
        'dzi_sposob_uzyt': 'gruntyRolne',
        'geometry': box(350000, 350000, 350025, 350040).wkb,
    })
    wiersz.update(zmiany)
    return wiersz


def zapisz_zrodlo(sciezka, wiersze, epsg=2180):
    liczby = {'tran_cena_brutto', 'tran_vat', 'nier_pow_gruntu', 'nier_cena_brutto',
              'nier_vat', 'dzi_pow_ewid', 'dzi_cena_brutto', 'dzi_vat'}
    pola = []
    for k in config.KOLUMNY_POTRZEBNE:
        typ = pa.float64() if k in liczby else pa.string()
        if k == 'dok_data': typ = pa.timestamp('ms')
        if k == 'geometry': typ = pa.binary()
        pola.append(pa.field(k, typ))
    geo = {'version': '1.1.0', 'primary_column': 'geometry', 'columns': {
        'geometry': {'encoding': 'WKB', 'crs': CRS.from_epsg(epsg).to_json_dict(), 'geometry_types': ['Polygon']}
    }}
    schemat = pa.schema(pola).with_metadata({b'geo': json.dumps(geo).encode()})
    pq.write_table(pa.Table.from_pylist(wiersze, schema=schemat), sciezka, row_group_size=2)


class CzyszczenieTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def uruchom(self, wiersze, partia=2, nazwa='wynik', woj=None):
        zrodlo = self.root / (nazwa + '.parquet')
        zapisz_zrodlo(zrodlo, wiersze)
        cel = self.root / nazwa
        with contextlib.redirect_stdout(io.StringIO()):
            oczysc_plik(zrodlo, cel, DATA_DO, partia, woj)
        df = pd.read_parquet(cel / 'transakcje.parquet')
        raport = pd.read_csv(cel / 'raport_czyszczenia.csv').set_index('powod')['wiersze'].to_dict()
        self.assertEqual(sum(raport.values()), len(wiersze))
        self.assertEqual(raport['zaakceptowane'], len(df))
        self.assertFalse(list(self.root.glob('.czyszczenie-*')))
        return df, raport

    def test_sklad_transakcji_przed_filtrami_i_granicami_partii(self):
        a = transakcja('powtorzona')
        b = transakcja('wielodzialkowa')
        wiersze = [a, b, transakcja('osobna'),
                   transakcja('wielodzialkowa', dzi_id_dzialki='020101_1.0001.99',
                              nier_rodzaj='nieruchomoscLokalowa', dok_data=None),
                   a, transakcja('powtorzona', tran_przestrzen_nazw='powiat-b')]
        df, raport = self.uruchom(wiersze)
        self.assertEqual(len(df), 3)
        self.assertEqual(df.klucz_transakcji.nunique(), 3)
        self.assertEqual(raport['powtorzone_wiersze'], 1)
        self.assertEqual(raport['transakcja_wielodzialkowa'], 2)
        df2, raport2 = self.uruchom(wiersze, partia=5, nazwa='inna_partia')
        pd.testing.assert_frame_equal(df, df2)
        self.assertEqual(raport, raport2)

    def test_sprzeczne_wersje_braki_i_prawdziwe_duplikaty(self):
        a=transakcja('wersje')
        b=transakcja('konflikt')
        c=transakcja('niepelna')
        df, raport = self.uruchom([
            a, transakcja('wersje', tran_wersja_id='2026-01-01'),
            b, transakcja('konflikt', tran_cena_brutto=200000),
            c, transakcja('niepelna', dzi_id_dzialki=None),
            transakcja('bez-klucza', tran_przestrzen_nazw=None),
        ])
        self.assertTrue(df.empty)
        self.assertEqual(raport['rozne_wersje_transakcji'], 2)
        self.assertEqual(raport['sprzeczne_wpisy_transakcji'], 2)
        self.assertEqual(raport['niepelny_sklad_transakcji'], 2)
        self.assertEqual(raport['brak_klucza_transakcji'], 1)

    def test_udzialy_ceny_i_daty(self):
        df, raport = self.uruchom([
            transakcja('pelny', nier_udzial=' 2 / 2; '),
            transakcja('ulamek', nier_udzial='1/2'),
            transakcja('brak', nier_udzial=None),
            transakcja('bledny', nier_udzial='1/0'),
            transakcja('wiele', nier_udzial='1/1;1/1'),
            transakcja('przyszla', dok_data=datetime(2026,10,3)),
            transakcja('stara', dok_data=datetime(14,1,1)),
            transakcja('zero', tran_cena_brutto=0),
            transakcja('inf', tran_cena_brutto=float('inf')),
            transakcja('ceny', nier_cena_brutto=50000),
            transakcja('droga', tran_cena_brutto=50000000),
            transakcja('tania', tran_cena_brutto=100),
        ])
        self.assertEqual(set(df.tran_lokalny_id_iip), {'pelny','droga','tania'})
        self.assertEqual(raport['data_z_przyszlosci'],1)
        self.assertEqual(raport['data_przed_zakresem'],1)
        self.assertEqual(raport['brak_lub_bledna_cena'],2)
        self.assertEqual(raport['niezgodne_ceny_skladowe'],1)

    def test_powierzchnia_i_geometria(self):
        df, raport = self.uruchom([
            transakcja('ha'), transakcja('m2',dzi_pow_ewid=1000),
            transakcja('bez-ewidencji',dzi_pow_ewid=None),
            transakcja('rozbieznosc',dzi_pow_ewid=5000),
            transakcja('bez-geometrii',geometry=None),
            transakcja('uszkodzona',geometry=b'not-wkb'),
            transakcja('pusta',geometry=Polygon().wkb),
            transakcja('ujemna',dzi_pow_ewid=-1),
        ])
        self.assertEqual(set(df.tran_lokalny_id_iip),{'ha','m2','bez-ewidencji','ujemna'})
        self.assertTrue(df.powierzchnia_m2.eq(1000).all())
        self.assertEqual(raport['rozbieznosc_powierzchni'],1)
        self.assertEqual(raport['brak_geometrii_do_weryfikacji'],3)
        self.assertTrue(df.teryt_gmina.eq('0201011').all())
        geo=json.loads(pq.ParquetFile(self.root/'wynik/transakcje.parquet').schema_arrow.metadata[b'geo'])
        self.assertEqual(geo['columns']['geometry']['crs']['id']['code'],2180)

    def test_dodanie_przyszlosci_nie_zmienia_wyniku(self):
        wiersze=[transakcja('teraz'),transakcja('inna',tran_cena_brutto=123456)]
        df,_=self.uruchom(wiersze)
        pozniej,_=self.uruchom(wiersze+[transakcja('pozniej',dok_data=datetime(2027,1,1))],nazwa='pozniej')
        pd.testing.assert_frame_equal(df,pozniej)

    def test_pusty_wynik_i_filtr_regionu(self):
        df,_=self.uruchom([],nazwa='pusty')
        self.assertTrue(df.empty)
        df,raport=self.uruchom([transakcja('a'),transakcja('b',dzi_id_dzialki='140101_1.0001.1')],woj='14')
        self.assertEqual(df.tran_lokalny_id_iip.tolist(),['b'])
        self.assertEqual(raport['inne_wojewodztwo'],1)

    def test_bledny_crs_i_ochrona_wyniku(self):
        zrodlo=self.root/'zrodlo.parquet'
        zapisz_zrodlo(zrodlo,[transakcja('a')],epsg=4326)
        with self.assertRaisesRegex(ValueError,'EPSG:2180'):
            oczysc_plik(zrodlo,self.root/'wynik',DATA_DO)
        self.assertFalse((self.root/'wynik').exists())
        self.uruchom([transakcja('a')])
        with self.assertRaises(FileExistsError):
            oczysc_plik(zrodlo,self.root/'wynik',DATA_DO)

    def test_brak_miejsca_nie_zostawia_wyniku(self):
        zrodlo=self.root/'zrodlo.parquet'
        zapisz_zrodlo(zrodlo,[transakcja('a')])
        with patch('etl.wczytanie_i_czyszczenie_cech.wczytywanie.shutil.disk_usage') as disk:
            disk.return_value.free=1
            with self.assertRaisesRegex(RuntimeError,'wolnego miejsca'):
                oczysc_plik(zrodlo,self.root/'wynik',DATA_DO)
        self.assertFalse((self.root/'wynik').exists())

    def test_blad_w_drugim_przebiegu_sprzata_indeks_i_nie_publikuje_wyniku(self):
        zrodlo=self.root/'zrodlo.parquet'
        zapisz_zrodlo(zrodlo,[transakcja('a')])
        with contextlib.redirect_stdout(io.StringIO()), patch(
            'etl.wczytanie_i_czyszczenie_cech.wczytywanie.wyczysc_partie',
            side_effect=RuntimeError('blad probny'),
        ):
            with self.assertRaisesRegex(RuntimeError,'blad probny'):
                oczysc_plik(zrodlo,self.root/'wynik',DATA_DO)
        self.assertFalse((self.root/'wynik').exists())
        self.assertFalse(list(self.root.glob('.czyszczenie-*')))


if __name__ == '__main__':
    unittest.main()
