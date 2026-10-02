import argparse
from datetime import date

import config
from etl.wczytanie_i_czyszczenie_cech.czyszczenie import WOJEWODZTWA
from etl.wczytanie_i_czyszczenie_cech.wczytywanie import oczysc_plik


def uruchom():
    parser = argparse.ArgumentParser(description='Czyszczenie RCN partiami, bez pobierania danych i liczenia OSM.')
    parser.add_argument('--wejscie', default=config.SCIEZKA_SUROWE)
    parser.add_argument('--wyjscie', default=config.SCIEZKA_OCZYSZCZONE)
    parser.add_argument('--data-do', type=date.fromisoformat, default=date.fromisoformat(config.DATA_DO))
    parser.add_argument('--partia', type=int, default=config.WIELKOSC_PARTII)
    parser.add_argument('--wojewodztwo', choices=sorted(WOJEWODZTWA), default=None)
    args = parser.parse_args()
    if args.data_do > date.today():
        parser.error('--data-do nie moze byc z przyszlosci')
    if args.data_do.year < config.ROK_OD:
        parser.error('--data-do jest przed poczatkiem zakresu badania')
    oczysc_plik(args.wejscie, args.wyjscie, args.data_do, args.partia, args.wojewodztwo)


if __name__ == '__main__':
    uruchom()
