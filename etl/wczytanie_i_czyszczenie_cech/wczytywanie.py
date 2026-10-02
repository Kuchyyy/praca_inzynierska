import json
import shutil
import time
from collections import Counter
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import CRS

import config
from etl.wczytanie_i_czyszczenie_cech.czyszczenie import wyczysc_partie
from etl.wczytanie_i_czyszczenie_cech.raport import zapisz_raport
from etl.wczytanie_i_czyszczenie_cech.transakcje import podsumuj_indeks, zbuduj_indeks


def oczysc_plik(wejscie, wyjscie, data_do, wielkosc_partii=25000, wojewodztwo=None):
    wejscie, wyjscie = Path(wejscie), Path(wyjscie)
    if wyjscie.exists():
        raise FileExistsError(f'Wynik juz istnieje: {wyjscie}. Podaj inny katalog --wyjscie.')
    if wielkosc_partii < 1:
        raise ValueError('Wielkosc partii musi byc dodatnia')
    if data_do > date.today() or data_do.year < config.ROK_OD:
        raise ValueError('Data odciecia musi byc miedzy poczatkiem badania a dzisiaj')
    parquet = pq.ParquetFile(wejscie)
    wymagane = set(config.KOLUMNY_POTRZEBNE)
    brak = wymagane - set(parquet.schema_arrow.names)
    if brak:
        raise ValueError(f'Brak kolumn: {sorted(brak)}')
    geo = json.loads((parquet.schema_arrow.metadata or {}).get(b'geo', b'{}'))
    kolumna_geo = geo.get('columns', {}).get('geometry', {})
    if (kolumna_geo.get('encoding') != 'WKB' or kolumna_geo.get('crs') is None
            or CRS.from_user_input(kolumna_geo['crs']).to_epsg() != 2180):
        raise ValueError('Oczekiwany GeoParquet z geometria WKB w EPSG:2180')
    stan_zrodla = (wejscie.stat().st_size, wejscie.stat().st_mtime_ns)
    wyjscie.parent.mkdir(parents=True, exist_ok=True)

    def sprawdz_miejsce():
        if shutil.disk_usage(wyjscie.parent).free < config.ZAPAS_DYSKU_GIB * 1024**3 + 256 * 1024**2:
            raise RuntimeError(f'Przerwano: potrzeba {config.ZAPAS_DYSKU_GIB} GiB wolnego miejsca')

    sprawdz_miejsce()
    start = time.monotonic()
    print(f'Wejscie: {wejscie}, {parquet.metadata.num_rows:,} wierszy', flush=True)
    print('Przebieg 1/2: sklad transakcji i duplikaty', flush=True)
    with TemporaryDirectory(prefix='.czyszczenie-', dir=wyjscie.parent) as tymczasowy:
        roboczy = Path(tymczasowy)
        baza, brak_klucza = zbuduj_indeks(parquet, roboczy / 'indeks.sqlite', wielkosc_partii, sprawdz_miejsce)
        writer = None
        try:
            liczniki = Counter(podsumuj_indeks(baza, brak_klucza))
            rozklad = Counter()
            zrodla_powierzchni = Counter()
            lata = Counter()
            kolumny = config.KOLUMNY_POTRZEBNE
            schemat = pa.schema([parquet.schema_arrow.field(k) for k in kolumny] + [
                pa.field(k, pa.string()) for k in [
                    'teryt_woj', 'teryt_powiat', 'teryt_gmina', 'teryt_obreb',
                    'status_udzialu', 'status_geometrii', 'zrodlo_powierzchni', 'klucz_transakcji'
                ]
            ] + [pa.field(k, pa.float64()) for k in [
                'pole_geom_m2', 'obwod_m', 'x_2180', 'y_2180', 'powierzchnia_m2', 'cena_m2'
            ]] + [pa.field('rok', pa.int32())])
            # Stary bbox opisuje surowy plik, a nie wynik filtrowania.
            geo_wyniku = {'version': geo['version'], 'primary_column': 'geometry', 'columns': {
                'geometry': {k: v for k, v in kolumna_geo.items() if k not in {'bbox', 'covering'}}
            }}
            schemat = schemat.with_metadata({b'geo': json.dumps(geo_wyniku).encode()})
            wynik = roboczy / 'wynik'
            wynik.mkdir()
            writer = pq.ParquetWriter(wynik / 'transakcje.parquet', schemat, compression='zstd')
            print('Przebieg 2/2: filtry, geometria i zapis partiami', flush=True)
            pozycja = 0
            zapisano = 0
            for partia in parquet.iter_batches(batch_size=wielkosc_partii, columns=kolumny):
                sprawdz_miejsce()
                indeksy = [r[0] - pozycja for r in baza.execute('''
                    SELECT pierwszy FROM transakcje
                    WHERE pierwszy >= ? AND pierwszy < ?
                      AND brak_dzialki = 0 AND wiele_dzialek = 0
                      AND wiele_wersji = 0 AND sprzeczne = 0
                    ORDER BY pierwszy
                ''', (pozycja, pozycja + len(partia)))]
                pozycja += len(partia)
                if not indeksy:
                    continue
                df = partia.take(pa.array(indeksy, type=pa.int64())).to_pandas()
                df = wyczysc_partie(df, data_do, liczniki, wojewodztwo)
                if not df.empty:
                    tabela = pa.Table.from_pandas(df, schema=schemat, preserve_index=False)
                    writer.write_table(tabela)
                    zapisano += len(df)
                    rozklad.update(df.groupby(['teryt_woj', df['dzi_sposob_uzyt'].fillna('brak_danych')]).size().to_dict())
                    zrodla_powierzchni.update(df['zrodlo_powierzchni'].value_counts().to_dict())
                    lata.update({str(k): v for k, v in df['rok'].value_counts().items()})
                if pozycja % (wielkosc_partii * 20) == 0:
                    print(f'  odczytano: {pozycja:,}, zapisano: {zapisano:,}', flush=True)
            writer.close()
            writer = None
            liczniki['zaakceptowane'] = zapisano
            if sum(liczniki.values()) != parquet.metadata.num_rows:
                raise RuntimeError('Raport nie bilansuje liczby wierszy')
            if stan_zrodla != (wejscie.stat().st_size, wejscie.stat().st_mtime_ns):
                raise RuntimeError('Plik zrodlowy zmienil sie podczas obliczen')
            zapisz_raport(wynik, liczniki, rozklad, {
                'plik_zrodlowy': str(wejscie.resolve()), 'bajty_zrodla': stan_zrodla[0],
                'data_do': data_do.isoformat(), 'rok_od': config.ROK_OD,
                'wojewodztwo': wojewodztwo, 'wielkosc_partii': wielkosc_partii,
                'wiersze_surowe': parquet.metadata.num_rows, 'wiersze_wynikowe': zapisano,
                'zrodla_powierzchni': dict(zrodla_powierzchni), 'lata': dict(sorted(lata.items())),
                'czas_sekundy': round(time.monotonic() - start, 2),
                'rozmiar_parquet_bajty': (wynik / 'transakcje.parquet').stat().st_size,
                'zasady': 'Jedna dzialka, pelny udzial, jedna spojna wersja; powierzchnia zweryfikowana geometria; bez percentyli i progow cen.'
            })
            sprawdz_miejsce()
            wynik.rename(wyjscie)
        finally:
            if writer is not None:
                writer.close()
            baza.close()
    print(f'Zapisano: {wyjscie}. Indeks tymczasowy usuniety.', flush=True)
    return wyjscie
