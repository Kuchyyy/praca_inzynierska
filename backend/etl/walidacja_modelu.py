import hashlib
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow as pa
import pyarrow.parquet as pq

import config
from etl.audyt_danych import zapisz_json
from etl.sasiedztwo_cenowe.polska import CECHY
from model.przygotowanie import przygotuj_walidacje


def przygotuj_dane_walidacyjne():
    katalog = Path(config.SCIEZKA_AUDYT)
    audyt = json.loads((katalog / 'podsumowanie.json').read_text())
    if audyt['status'] != 'OK':
        raise ValueError('Najpierw wymagany poprawny audyt danych')
    cel = katalog / 'walidacja'
    podpis = {'sha256_danych': audyt['sha256'], 'walidacja_od': config.WALIDACJA_OD,
              'test_od': config.TEST_OD}
    podpis['kod'] = {}
    for nazwa in [__file__, 'model/przygotowanie.py', 'etl/sasiedztwo_cenowe/polska.py']:
        podpis['kod'][Path(nazwa).name] = hashlib.sha256(Path(nazwa).read_bytes()).hexdigest()
    wejscie = Path(config.SCIEZKA_PELNE_CECHY) / 'transakcje.parquet'
    skrot = hashlib.sha256()
    with wejscie.open('rb') as plik:
        for blok in iter(lambda: plik.read(8 * 1024**2), b''):
            skrot.update(blok)
    if skrot.hexdigest() != audyt['sha256']:
        raise ValueError('Dane zmienily sie od audytu; uruchom audyt ponownie')
    if (cel / 'podsumowanie.json').exists():
        poprzedni = json.loads((cel / 'podsumowanie.json').read_text())
        if poprzedni['podpis'] == podpis and (cel / 'sasiedztwo.parquet').exists():
            print('Korzystam z gotowych cech walidacji czasowej.', flush=True)
            return poprzedni
        raise FileExistsError('Inny podzial walidacji juz istnieje; ustaw nowa SCIEZKA_AUDYT')
    if cel.exists():
        raise FileExistsError(f'Niekompletny katalog wyniku: {cel}')
    if shutil.disk_usage(katalog).free < (config.ZAPAS_DYSKU_GIB + 1) * 1024**3:
        raise RuntimeError('Brak zapasu dysku dla walidacji')
    kolumny = ['klucz_transakcji', 'dok_data', 'cena_m2', 'dzi_id_dzialki',
               'dzi_sposob_uzyt', 'teryt_gmina', 'teryt_obreb', 'x_2180', 'y_2180']
    dane = pq.read_table(wejscie, columns=kolumny).to_pandas()
    dane = przygotuj_walidacje(dane, config.WALIDACJA_OD, config.TEST_OD)
    raport = {'podpis': podpis, 'wiersze': len(dane), 'podzial': dane.zbior.value_counts().to_dict(),
              'laczenie': 'Po klucz_transakcji, validate=one_to_one. Zastap 8 cech sasiedztwa i zbior. Nie dolaczaj testu koncowego.',
              'referencje': 'Tylko przed WALIDACJA_OD, scisle wczesniejszy dzien i inna dzialka.'}
    wynik = dane[['klucz_transakcji', 'zbior'] + CECHY]
    with TemporaryDirectory(prefix='.walidacja-', dir=katalog) as roboczy:
        roboczy = Path(roboczy)
        schemat = pa.Schema.from_pandas(wynik, preserve_index=False)
        with pq.ParquetWriter(roboczy / 'sasiedztwo.parquet', schemat, compression='zstd') as zapis:
            for start in range(0, len(wynik), config.WIELKOSC_PARTII):
                if shutil.disk_usage(roboczy).free < config.ZAPAS_DYSKU_GIB * 1024**3:
                    raise RuntimeError('Brak zapasu dysku podczas zapisu walidacji')
                partia = wynik.iloc[start:start + config.WIELKOSC_PARTII]
                zapis.write_table(pa.Table.from_pandas(partia, schema=schemat, preserve_index=False))
        zapisz_json(roboczy / 'podsumowanie.json', raport)
        roboczy.rename(cel)
    print(json.dumps(raport, ensure_ascii=False, indent=2), flush=True)
    return raport


if __name__ == '__main__':
    przygotuj_dane_walidacyjne()
