import hashlib
import json
import shutil
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import psycopg
from psycopg import sql
import shapely

import config
from wycena.baza import ustawienia_bazy


def polacz():
    # Bez .env i bez hasła łączymy się z bazą, która nie sprawdza haseł.
    ustawienia = ustawienia_bazy()
    return psycopg.connect(host=config.POSTGRES_HOST,
                           port=ustawienia.get('POSTGRES_PORT', '5432'),
                           dbname=ustawienia.get('POSTGRES_DB', 'dzialki'),
                           user=ustawienia.get('POSTGRES_USER', 'postgres'),
                           password=ustawienia.get('POSTGRES_PASSWORD') or None,
                           autocommit=True, application_name='import_postgis')


def sprawdz_miejsce():
    if shutil.disk_usage(Path.cwd()).free < (config.ZAPAS_DYSKU_GIB + 0.5) * 1024**3:
        raise RuntimeError('Zatrzymano import, aby zachowac 10 GiB zapasu. Zwolnij miejsce i wznow ta sama komende.')


def importuj_plik(baza, plik, nazwa):
    sprawdz_miejsce()
    skrot = hashlib.sha256()
    with plik.open('rb') as dane:
        for blok in iter(lambda: dane.read(8 * 1024**2), b''):
            skrot.update(blok)
    podpis = skrot.hexdigest()
    parquet = pq.ParquetFile(plik)
    liczba = parquet.metadata.num_rows
    if nazwa == 'transakcje':
        geo = json.loads(parquet.schema_arrow.metadata[b'geo'])
        crs = geo['columns']['geometry']['crs']
        if crs['id']['code'] != 2180:
            raise ValueError('Nieoczekiwany CRS transakcji')
    else:
        opis = json.loads((plik.parent / 'opis.json').read_text())
        if opis['crs'] != 'EPSG:2180' or opis['liczniki'][plik.stem] != liczba:
            raise ValueError('Niezgodny opis warstwy OSM')

    stan = baza.execute('SELECT sha256, wiersze, zakonczone FROM importy.stan WHERE tabela=%s', (nazwa,)).fetchone()
    if stan and stan[0] != podpis:
        raise ValueError(f'Zmienione zrodlo {nazwa}; istniejacy import nie bedzie nadpisany')
    if stan and stan[2]:
        aktualne = baza.execute(sql.SQL('SELECT count(*) FROM dane.{}').format(sql.Identifier(nazwa))).fetchone()[0]
        if aktualne != liczba:
            raise ValueError(f'Zmieniona liczba rekordow gotowej tabeli {nazwa}')
        print(f'{nazwa}: gotowe, {liczba:,} rekordow', flush=True)
        return {'wiersze': liczba, 'sha256': podpis}

    tabela = sql.Identifier('importy', nazwa)
    pola = []
    for pole in parquet.schema_arrow:
        if pole.name == 'geometry':
            typ = 'geometry(Geometry,2180) NOT NULL'
        elif pa.types.is_string(pole.type):
            typ = 'text'
        elif pa.types.is_boolean(pole.type):
            typ = 'boolean'
        elif pa.types.is_integer(pole.type):
            typ = 'bigint'
        elif pa.types.is_floating(pole.type):
            typ = 'double precision'
        elif pa.types.is_timestamp(pole.type):
            typ = 'timestamp without time zone'
        else:
            raise ValueError(f'Nieobslugiwany typ {pole}')
        pola.append(sql.SQL('{} {}').format(sql.Identifier(pole.name), sql.SQL(typ)))
    if stan is None:
        with baza.transaction():
            baza.execute(sql.SQL('CREATE TABLE {} ({})').format(tabela, sql.SQL(', ').join(pola)))
            baza.execute('INSERT INTO importy.stan(tabela,sha256,plik,wiersze,zakonczone) VALUES (%s,%s,%s,0,false)',
                         (nazwa, podpis, str(plik)))
        wykonane = 0
    else:
        wykonane = stan[1]
    aktualne = baza.execute(sql.SQL('SELECT count(*) FROM {}').format(tabela)).fetchone()[0]
    if aktualne != wykonane:
        raise ValueError(f'Niezgodny stan wznowienia {nazwa}')
    kolumny = parquet.schema_arrow.names
    zapytanie = sql.SQL('COPY {} ({}) FROM STDIN').format(tabela, sql.SQL(', ').join(map(sql.Identifier, kolumny)))
    pominieto = 0
    poczatek = time.monotonic()
    ostatni_log = poczatek
    for partia in parquet.iter_batches(batch_size=config.POSTGRES_PARTIA):
        koniec = pominieto + partia.num_rows
        if koniec <= wykonane:
            pominieto = koniec
            continue
        if pominieto < wykonane:
            partia = partia.slice(wykonane - pominieto)
        pominieto = koniec
        sprawdz_miejsce()
        wartosci = []
        for pole, kolumna in zip(parquet.schema_arrow, partia.columns):
            if pole.name == 'geometry':
                geometrie = shapely.from_wkb(kolumna.to_numpy(zero_copy_only=False))
                if shapely.is_missing(geometrie).any() or shapely.is_empty(geometrie).any():
                    raise ValueError(f'Pusta geometria w {nazwa}')
                ewkb = shapely.to_wkb(shapely.set_srid(geometrie, 2180), hex=True, include_srid=True)
                wartosci.append(ewkb)
            else:
                wartosci.append(kolumna.to_pylist())
        with baza.transaction():
            with baza.cursor().copy(zapytanie) as zapis:
                for rekord in zip(*wartosci):
                    zapis.write_row(rekord)
            wykonane += partia.num_rows
            baza.execute('UPDATE importy.stan SET wiersze=%s, aktualizacja=now() WHERE tabela=%s', (wykonane, nazwa))
        if time.monotonic() - ostatni_log > 10 or wykonane == liczba:
            print(f'{nazwa}: {wykonane:,}/{liczba:,}', flush=True)
            ostatni_log = time.monotonic()

    sprawdz_miejsce()
    print(f'{nazwa}: weryfikacja geometrii i indeksy', flush=True)
    kontrola = baza.execute(sql.SQL('SELECT count(*), count(*) FILTER (WHERE NOT ST_IsValid(geometry)) FROM {}').format(tabela)).fetchone()
    if kontrola != (liczba, 0):
        raise ValueError(f'Niepoprawna liczba lub geometrie {nazwa}: {kontrola}')
    # Publikacja i indeksy razem; przerwanie zostawia kompletne partie do wznowienia.
    with baza.transaction():
        if nazwa == 'transakcje':
            baza.execute(sql.SQL('ALTER TABLE {} ADD PRIMARY KEY (klucz_transakcji)').format(tabela))
            baza.execute(sql.SQL('ALTER TABLE {} ADD COLUMN srodek geometry(Point,2180) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(x_2180,y_2180),2180)) STORED').format(tabela))
            for nazwa_indeksu, wyrazenie in [
                ('transakcje_srodek_gist', 'USING gist (srodek)'),
                ('transakcje_data_idx', '(dok_data)'),
                ('transakcje_dzialka_idx', '(dzi_id_dzialki)'),
                ('transakcje_gmina_data_idx', '(teryt_gmina, dok_data)'),
                ('transakcje_obreb_data_idx', '(teryt_obreb, dok_data)'),
            ]:
                baza.execute(sql.SQL('CREATE INDEX {} ON {} {}').format(sql.Identifier(nazwa_indeksu), tabela, sql.SQL(wyrazenie)))
        baza.execute(sql.SQL('CREATE INDEX {} ON {} USING gist (geometry)').format(sql.Identifier(nazwa + '_geom_gist'), tabela))
        sprawdz_miejsce()
        baza.execute(sql.SQL('ALTER TABLE {} SET SCHEMA dane').format(tabela))
        baza.execute(sql.SQL('GRANT SELECT, INSERT, UPDATE, DELETE ON dane.{} TO dzialki_app').format(sql.Identifier(nazwa)))
        baza.execute('UPDATE importy.stan SET zakonczone=true, aktualizacja=now() WHERE tabela=%s', (nazwa,))
    baza.execute(sql.SQL('ANALYZE dane.{}').format(sql.Identifier(nazwa)))
    rozmiar = baza.execute('SELECT pg_total_relation_size(%s)', ('dane.' + nazwa,)).fetchone()[0]
    print(f'{nazwa}: zakonczono, {rozmiar / 1024**2:.0f} MiB', flush=True)
    return {'wiersze': liczba, 'sha256': podpis, 'bajty_tabeli': rozmiar, 'bledne_geometrie': 0}


def importuj_dane():
    pliki = [(Path(config.SCIEZKA_PELNE_CECHY) / 'transakcje.parquet', 'transakcje')]
    osm = sorted(Path(config.SCIEZKA_WARSTWY_OSM).glob('*.parquet'), key=lambda p: p.stat().st_size)
    if not osm:
        raise ValueError('Brak warstw OSM')
    pliki.extend((p, 'osm_' + p.stem) for p in osm)
    raport = {}
    with polacz() as baza:
        if not baza.execute('SELECT pg_try_advisory_lock(218017) ').fetchone()[0]:
            raise RuntimeError('Inna kopia importu juz dziala')
        baza.execute('CREATE SCHEMA IF NOT EXISTS importy')
        baza.execute('CREATE TABLE IF NOT EXISTS importy.stan (tabela text PRIMARY KEY, sha256 text NOT NULL, plik text NOT NULL, wiersze bigint NOT NULL, zakonczone boolean NOT NULL, aktualizacja timestamptz NOT NULL DEFAULT now())')
        for plik, nazwa in pliki:
            raport[nazwa] = importuj_plik(baza, plik, nazwa)
            cel = Path(config.SCIEZKA_RAPORT_IMPORTU)
            tymczasowy = cel.with_suffix('.tmp')
            tymczasowy.write_text(json.dumps(raport, ensure_ascii=False, indent=2))
            tymczasowy.replace(cel)
        print('Import zakonczony.', flush=True)


if __name__ == '__main__':
    importuj_dane()
