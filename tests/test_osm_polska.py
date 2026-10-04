import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely
from pyproj import Transformer
from shapely.geometry import Point, LineString, box

import config
from etl.cechy_osm.warstwy import wybierz_warstwy, przygotuj_warstwy
from etl.cechy_osm.polska import odleglosci_do_geometrii, pokrycie, policz_osm


class OSMPolskaTest(unittest.TestCase):
    def test_droga_polna_i_nieznana_nawierzchnia(self):
        self.assertNotIn('drogi', wybierz_warstwy({'highway':'track'}, 'linia')[0])
        self.assertNotIn('utwardzone', wybierz_warstwy({'highway':'residential'}, 'linia')[0])
        self.assertIn('utwardzone', wybierz_warstwy({'highway':'residential','surface':'asphalt'}, 'linia')[0])
        self.assertIn('szkoly', wybierz_warstwy({'amenity':'school'}, 'obszar')[0])

    def test_odleglosc_do_odcinka_nie_centroidu(self):
        punkty = np.array([Point(0, 0), Point(100, 1)])
        geometrie = np.array([LineString([(0, 5), (1000, 5)])])
        np.testing.assert_allclose(odleglosci_do_geometrii(punkty, geometrie), [5, 4])
        self.assertTrue(np.isnan(odleglosci_do_geometrii(punkty, np.array([]))).all())

    def test_nakladajace_sie_lasy_nie_podwajaja_pola(self):
        punkty = np.array([Point(0, 0), Point(100,100)])
        geometrie = np.array([box(-20,-20,20,20),box(-20,-20,20,20)])
        np.testing.assert_allclose(pokrycie(punkty, geometrie, 10), [1,0])

    def test_pbf_strumieniowo_obszary_i_wynik_tylko_do_modelu(self):
        with tempfile.TemporaryDirectory() as katalog:
            root=Path(katalog)
            zrodlo=root/'mapa.osm'
            zrodlo.write_text('''<?xml version="1.0"?><osm version="0.6">
<node id="1" lat="52" lon="19"><tag k="amenity" v="school"/></node>
<node id="2" lat="52.001" lon="19"/>
<node id="3" lat="52.001" lon="19.001"/>
<node id="4" lat="52" lon="19.001"/>
<way id="10"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/><tag k="building" v="house"/><tag k="amenity" v="kindergarten"/></way>
</osm>''')
            wejscie=root/'wejscie';wejscie.mkdir()
            x,y=Transformer.from_crs(4326,2180,always_xy=True).transform(19,52)
            pd.DataFrame({'klucz_transakcji':['a','b'],'x_2180':[x,x],'y_2180':[y,y],'do_modelu':[True,False]}).to_parquet(wejscie/'transakcje.parquet')
            with patch.multiple(config, SCIEZKA_OSM=str(zrodlo),SCIEZKA_WARSTWY_OSM=str(root/'warstwy'),SCIEZKA_POSREDNIE=str(root),SCIEZKA_PO_EGIB=str(wejscie),SCIEZKA_CECHY_OSM=str(root/'wynik')):
                with patch('builtins.print'):
                    policz_osm()
                dane=pd.read_parquet(root/'wynik/transakcje.parquet')
                self.assertEqual(dane.klucz_transakcji.tolist(),['a'])
                self.assertAlmostEqual(dane.odl_szkola_m.iloc[0],0)
                self.assertAlmostEqual(dane.odl_przedszkole_m.iloc[0],0)
                self.assertEqual(dane.liczba_budynkow_250m.iloc[0],1)
                self.assertTrue(np.isnan(dane.odl_woda_m.iloc[0]))
                self.assertEqual(pq.ParquetFile(root/'warstwy/budynki.parquet').metadata.num_rows,1)
                self.assertFalse(list(root.glob('.osm-*')))
                self.assertEqual(przygotuj_warstwy(), root/'warstwy')
