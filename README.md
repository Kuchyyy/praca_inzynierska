# Predykcja cen działek — przygotowanie danych

Program czyta surowe dane z Rejestru Cen Nieruchomości, czyści je i buduje zestaw cech
do uczenia maszynowego.

To pierwszy etap pracy. Nie ma tu jeszcze modeli, bazy danych ani interfejsu.

## Uruchomienie

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Plik z danymi wrzuć do `dane/surowe/` pod nazwą `02_transakcje_ceny_dzialki.parquet`, potem:

```bash
python main.py
```

To samo w Dockerze, z katalogiem `dane/` zamontowanym z dysku:

```bash
docker compose up --build
```

## Co robi program

```
dane/surowe/02_transakcje_ceny_dzialki.parquet     1 186 343 wiersze
        |
        v
   czyszczenie (kroki 1-12)
        |
        v
   geometria
        |
        v
   czyszczenie (kroki 13-15)
        |
        v
   cechy podstawowe + geometryczne
        |
        v
dane/gotowe/dane_z_cechami.parquet                 76 346 transakcji
```

Geometria jest liczona przed filtrami powierzchni i ceny, bo te filtry potrzebują
powierzchni w metrach kwadratowych.

## Podgląd

```bash
python zobacz.py
python do_excela.py
```

`do_excela.py` zapisuje 2000 losowych transakcji do CSV. Cały zbiór:
ustaw `ILE_WIERSZY = None`.

## Wynik

| Plik | Co zawiera |
|---|---|
| `dane/gotowe/dane_z_cechami.parquet` | Gotowy zbiór |
| `dane/gotowe/raport_czyszczenia.csv` | Ile rekordów odpadło na każdym kroku |
| `dane/posrednie/odrzucone/` | Rekordy odrzucone na każdym kroku |

## Struktura

```
config.py                       ścieżki i progi
main.py                         kolejność etapów
CECHY.md                        opis każdej cechy

etl/wczytywanie.py              wczytanie pliku Parquet
etl/czyszczenie.py              filtry
etl/geometria.py                granice działki i jednostki powierzchni
etl/cechy_podstawowe.py         cechy z kolumn pliku
etl/cechy_geometryczne.py       cechy z kształtu działki
etl/raport.py                   statystyki

zobacz.py                       podgląd gotowych danych
do_excela.py                    eksport próbki do CSV
```

Opis cech i dalszych etapów jest w `CECHY.md`.
# Praca_in-ynierska
