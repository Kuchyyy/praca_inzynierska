import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

import config
from etl.sasiedztwo_cenowe.polska import CECHY


def zapisz_json(sciezka, dane):
    roboczy = sciezka.with_suffix('.tmp')
    roboczy.write_text(json.dumps(dane, ensure_ascii=False, indent=2, allow_nan=False))
    roboczy.replace(sciezka)


def dostepnosc_cech(manifest):
    wynik = []
    for nazwa in manifest['cechy']:
        mapa = True
        if nazwa in {'tran_sprzedajacy', 'nier_prawo', 'dzi_sposob_uzyt'}:
            zrodlo = 'formularz'
            wymaganie = 'Uzytkownik podaje kategorie zgodna ze slownikiem RCN; brak pozostaje brakiem.'
            mapa = False
        elif nazwa.startswith('przezn_') or nazwa == 'ma_wpis_przeznaczenia':
            zrodlo = 'formularz_przeznaczenie'
            wymaganie = 'Potwierdzone przeznaczenie w slowniku RCN; brak informacji nie oznacza braku MPZP.'
            mapa = False
        elif nazwa == 'miejscowosc':
            zrodlo = 'adres_rcn'
            wymaganie = 'Nazwa z historycznego adresu RCN; wykluczona z obu wariantow.'
            mapa = False
        elif nazwa in CECHY:
            zrodlo = 'referencje_rcn'
            wymaganie = 'Wczesniejsze znane ceny, bez tej samej dzialki; wymaga bazy referencyjnej i daty wyceny.'
            if nazwa.endswith('ten_sam_uzytek'):
                wymaganie += ' Wymaga rowniez uzytkowania z formularza.'
                mapa = False
        elif nazwa in {'rok', 'miesiace_od_2015'}:
            zrodlo = 'data_wyceny'
            wymaganie = 'Data zadana dla wyceny; w treningu data transakcji.'
        elif nazwa.startswith('teryt_'):
            zrodlo = 'identyfikator_dzialki'
            wymaganie = 'Zweryfikowany identyfikator dzialki i kod administracyjny.'
        elif nazwa in {'x_2180', 'y_2180', 'powierzchnia_m2', 'log_powierzchnia', 'wskaznik_zwartosci'}:
            zrodlo = 'geometria'
            wymaganie = 'Pelny poprawny poligon EPSG:2180; ta sama definicja srodka i weryfikacji powierzchni co w ETL.'
        else:
            zrodlo = 'osm'
            wymaganie = 'Warstwy OSM i te same funkcje odleglosci/buforow co w ETL; brak warstwy nie oznacza zera.'
        wynik.append({'cecha': nazwa, 'zrodlo': zrodlo, 'wariant_mapa': mapa, 'wymaganie': wymaganie})
    return wynik


def profil_kolumny(seria, trening, kategoria=False):
    wynik = {}
    for zbior, maska in [('trening', trening), ('test', ~trening)]:
        wartosci = seria[maska]
        opis = {'wiersze': len(wartosci), 'braki': int(wartosci.isna().sum()),
                'rozne': int(wartosci.nunique())}
        if kategoria:
            opis['najczestsze'] = {str(k): int(v) for k, v in wartosci.value_counts().head(10).items()}
            if zbior == 'test':
                znane = set(seria[trening].dropna())
                opis['nieznane_w_treningu'] = int((wartosci.notna() & ~wartosci.isin(znane)).sum())
        else:
            liczby = wartosci.to_numpy(dtype=float, na_value=np.nan)
            opis['nieskonczone'] = int(np.isinf(liczby).sum())
            dobre = liczby[np.isfinite(liczby)]
            opis['kwantyle'] = {}
            if len(dobre):
                for q in [0, 0.001, 0.01, 0.5, 0.99, 0.999, 1]:
                    opis['kwantyle'][str(q)] = float(np.quantile(dobre, q))
        wynik[zbior] = opis
    return wynik


def audytuj_dane():
    wejscie = Path(config.SCIEZKA_PELNE_CECHY) / 'transakcje.parquet'
    cel = Path(config.SCIEZKA_AUDYT)
    cel.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(cel).free < config.ZAPAS_DYSKU_GIB * 1024**3:
        raise RuntimeError('Brak wymaganego zapasu dysku')
    manifest_plik = wejscie.parent / 'cechy_modelu.json'
    manifest = json.loads(manifest_plik.read_text())
    if manifest['test_od'] != config.TEST_OD:
        raise ValueError('Zmieniona data testu wymaga przeliczenia sasiedztwa')

    skrot = hashlib.sha256()
    with wejscie.open('rb') as plik:
        for blok in iter(lambda: plik.read(8 * 1024**2), b''):
            skrot.update(blok)
    podpis = {'sha256': skrot.hexdigest(), 'manifest': manifest,
              'kod_audytu': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'powierzchnia': [config.POWIERZCHNIA_MIN, config.POWIERZCHNIA_MAX],
              'data_do': config.DATA_DO, 'walidacja_od': config.WALIDACJA_OD}
    if not pd.Timestamp(f'{config.ROK_OD}-01-01') < pd.Timestamp(config.WALIDACJA_OD) < pd.Timestamp(config.TEST_OD):
        raise ValueError('Walidacja musi byc wewnatrz okresu treningowego')
    cache = cel / 'postep.json'
    stan = {'podpis': podpis, 'profile': {}}
    if cache.exists():
        poprzedni = json.loads(cache.read_text())
        if poprzedni['podpis'] == podpis:
            stan = poprzedni
    # Poprzedni sukces nie moze pozostac po przerwaniu nowego audytu.
    zapisz_json(cel / 'podsumowanie.json', {'status': 'w_trakcie', 'sha256': podpis['sha256']})
    parquet = pq.ParquetFile(wejscie)
    kontrolne = ['klucz_transakcji', 'dzi_id_dzialki', 'dok_data', 'zbior', 'cena_m2',
                 'powierzchnia_m2', 'udzial_sprzedany', 'do_modelu', 'teryt_woj',
                 'x_2180', 'y_2180', 'tran_cena_brutto']
    # Tylko waska tabela kontrolna; cechy czytamy pojedynczo, bez geometrii.
    dane = parquet.read(columns=kontrolne).to_pandas()
    trening = dane.dok_data.lt(pd.Timestamp(config.TEST_OD))
    bledy = []
    if dane.dok_data.isna().any() or not dane.dok_data.between(f'{config.ROK_OD}-01-01', config.DATA_DO).all():
        bledy.append('Niepoprawne daty')
    if not dane.zbior.eq(np.where(trening, 'trening', 'test')).all():
        bledy.append('Niezgodny podzial czasowy')
    if not trening.any() or trening.all():
        bledy.append('Pusty trening lub test')
    if dane.klucz_transakcji.isna().any() or not dane.klucz_transakcji.is_unique:
        bledy.append('Brak lub duplikat klucza transakcji')
    if dane.dzi_id_dzialki.isna().any():
        bledy.append('Brak identyfikatora dzialki')
    for nazwa in ['cena_m2', 'powierzchnia_m2', 'udzial_sprzedany', 'tran_cena_brutto']:
        if not (np.isfinite(dane[nazwa]) & dane[nazwa].gt(0)).all():
            bledy.append('Niepoprawne wartosci: ' + nazwa)
    if not dane.udzial_sprzedany.le(1).all() or not dane.do_modelu.eq(True).all():
        bledy.append('Niepoprawny udzial lub flaga do_modelu')
    if not dane.powierzchnia_m2.between(config.POWIERZCHNIA_MIN, config.POWIERZCHNIA_MAX).all():
        bledy.append('Powierzchnia poza zakresem')
    oczekiwana = dane.tran_cena_brutto / (dane.powierzchnia_m2 * dane.udzial_sprzedany)
    if not np.isclose(dane.cena_m2, oczekiwana, rtol=1e-8, atol=1e-8).all():
        bledy.append('Cena m2 niezgodna z cena transakcji, powierzchnia i udzialem')
    if not np.isfinite(dane[['x_2180', 'y_2180']]).all().all():
        bledy.append('Brak poprawnych wspolrzednych')

    kolumny = list(dict.fromkeys(manifest['cechy'] + ['cena_m2', 'udzial_sprzedany']))
    for i, nazwa in enumerate(kolumny):
        if nazwa not in stan['profile']:
            serie = []
            for partia in parquet.iter_batches(batch_size=config.WIELKOSC_PARTII, columns=[nazwa]):
                serie.append(partia.column(0).to_pandas())
            seria = pd.concat(serie, ignore_index=True)
            stan['profile'][nazwa] = profil_kolumny(seria, trening, nazwa in manifest['kategoryczne'])
            zapisz_json(cache, stan)
        if i % 10 == 0:
            print(f'Audyt cech: {i + 1}/{len(kolumny)}', flush=True)
    profile = stan['profile']
    for nazwa, profil in profile.items():
        if any(p.get('nieskonczone', 0) for p in profil.values()):
            bledy.append('Nieskonczone wartosci: ' + nazwa)
        for opis in profil.values():
            kwantyle = opis.get('kwantyle', {})
            if not kwantyle:
                continue
            minimum, maksimum = kwantyle['0'], kwantyle['1']
            if nazwa.startswith(('odl_', 'liczba_', 'mediana_', 'ludnosc_')) and minimum < 0:
                bledy.append('Ujemna odleglosc, liczba lub mediana: ' + nazwa)
            if nazwa.startswith(('udzial_', 'czy_', 'przezn_')) or nazwa in {'wskaznik_zwartosci', 'ma_wpis_przeznaczenia'}:
                if minimum < 0 or maksimum > 1 + 1e-9:
                    bledy.append('Wartosc poza zakresem 0-1: ' + nazwa)

    dostepnosc = dostepnosc_cech(manifest)
    stale = [n for n in manifest['cechy'] if profile[n]['trening']['rozne'] <= 1]
    warianty = {}
    for wariant in ['mapa', 'formularz']:
        cechy = [p['cecha'] for p in dostepnosc
                 if (p['wariant_mapa'] or wariant == 'formularz')
                 and p['cecha'] != 'miejscowosc' and p['cecha'] not in stale]
        warianty[wariant] = {'cechy': cechy,
                            'kategoryczne': [n for n in cechy if n in manifest['kategoryczne']],
                            'liczbowe': [n for n in cechy if n not in manifest['kategoryczne']]}
    kontrakt = {'target': 'cena_m2', 'wariant_domyslny': 'mapa', 'warianty': warianty,
                'usuniete_stale_na_treningu': stale, 'sha256_danych': podpis['sha256'],
                'test_od': config.TEST_OD, 'walidacja_od': config.WALIDACJA_OD,
                'imputacja': 'Mediany i wskazniki brakow dla liczb; stala __BRAK__ dla kategorii; fit tylko na treningu danego podzialu.',
                'walidacja': 'Przed walidacja przelicz 8 cech sasiedztwa z odcieciem WALIDACJA_OD. Test koncowy pozostaje nietkniety podczas doboru modelu.',
                'udzialy': 'Wariant podstawowy zawiera wszystkie znane udzialy. Porownaj trening tylko na pelnych udzialach na tym samym tescie; przelicz takze referencje cenowe.',
                'ceny_skrajne': 'Bez automatycznego odcinania. Progi raportu pochodza tylko z treningu.',
                'wdrozenie': 'Kontrakt wejsc; nie oznacza gotowego API. Wymaga geometrii, warstw OSM i bazy referencyjnej RCN.'}
    pd.DataFrame(dostepnosc).to_csv(cel / 'dostepnosc_cech.csv', index=False)
    zapisz_json(cel / 'cechy_modelu.json', kontrakt)
    zapisz_json(cel / 'profile.json', profile)
    pokrycie = dane.groupby(['zbior', 'teryt_woj'], dropna=False).size().rename('wiersze')
    pokrycie.to_csv(cel / 'pokrycie_wojewodztw.csv')
    granice = dane.loc[trening, 'cena_m2'].quantile([0.001, 0.999])
    skrajne = dane.cena_m2.lt(granice.iloc[0]) | dane.cena_m2.gt(granice.iloc[1])
    dane.loc[skrajne, kontrolne].to_csv(cel / 'ceny_do_przegladu.csv', index=False)
    udzialy = dane.assign(udzial=np.where(dane.udzial_sprzedany.eq(1), 'pelny', 'czesciowy'))
    udzialy.groupby(['zbior', 'udzial']).agg(wiersze=('cena_m2', 'size'), mediana_cena_m2=('cena_m2', 'median')).to_csv(cel / 'udzialy.csv')
    wspolne = set(dane.loc[trening, 'dzi_id_dzialki']) & set(dane.loc[~trening, 'dzi_id_dzialki'])
    raport = {'status': 'OK' if not bledy else 'BLAD', 'bledy': bledy,
              'wiersze': len(dane), 'podzial': dane.zbior.value_counts().to_dict(),
              'cechy_wariantow': {n: len(w['cechy']) for n, w in warianty.items()},
              'stale_na_treningu': stale, 'ceny_do_przegladu': int(skrajne.sum()),
              'progi_cen_z_treningu': granice.tolist(),
              'udzialy_czesciowe': int(dane.udzial_sprzedany.lt(1).sum()),
              'dzialki_w_treningu_i_tescie': len(wspolne),
              'sha256': podpis['sha256'],
              'ograniczenia': ['OSM i EGiB opisuja obecny, nie historyczny stan.',
                               'Braki cech pozostaja do imputacji na treningu.',
                               'Cena udzialu przeliczona proporcjonalnie nie potwierdza ceny calej dzialki.',
                               'Wspolne dzialki wymagaja osobnej oceny testu na niewidzianych dzialkach.',
                               'Walidacja czasowa wymaga ponownego obliczenia sasiedztwa.']}
    zapisz_json(cel / 'podsumowanie.json', raport)
    print(json.dumps(raport, ensure_ascii=False, indent=2), flush=True)
    if bledy:
        raise ValueError('Audyt wykryl bledy: ' + '; '.join(bledy))
    return raport


if __name__ == '__main__':
    audytuj_dane()
