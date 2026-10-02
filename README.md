# Predykcja cen działek — przygotowanie danych

Bieżący etap czyści krajowy Rejestr Cen Nieruchomości partiami. Zapisuje
jeden GeoParquet z geometrią, powierzchnią i ceną za m² oraz małe raporty.
Nie pobiera danych, nie liczy OSM ani sąsiedztwa cenowego i nie uczy modeli.

## Uruchomienie

Z głównego katalogu repo:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Domyślne źródło: `db/dane/surowe/rcn/0_transakcje_ceny_dzialki.parquet`.
Wynik: `db/dane/gotowe/polska_oczyszczone/`.
Data odcięcia jest jawna: `2026-10-02`, ustawiona w `config.py`.

Przebieg z 02.10.2026: **14 795 036 surowych wierszy → 488 960 transakcji**
ze wszystkich 16 województw. Parquet wyniku zajmuje 111,47 MB; obliczenia
trwały około 353 sekund. Są to wyniki opisanych poniżej, ostrożnych filtrów,
a nie liczba wszystkich sprzedaży gruntów w kraju.

Przykład dla Dolnego Śląska, nadal z kontrolą składu transakcji w całym kraju:

```bash
python main.py --wojewodztwo 02 --wyjscie db/dane/gotowe/dolnoslaskie_oczyszczone
```

Można też podać `--wejscie`, `--data-do YYYY-MM-DD` i `--partia 25000`.
Istniejący katalog wyniku nie jest nadpisywany. Do ponownego porównania
należy podać nowy `--wyjscie`, uwzględniając miejsce na dysku.

Docker używa tego samego katalogu danych:

```bash
docker compose up --build
```

## Zasady czyszczenia

- Klucz transakcji to para: przestrzeń nazw i lokalny identyfikator.
  Brak któregoś składnika oznacza odrzucenie, bez zgadywania powiatu.
- Skład transakcji sprawdzany jest w całym źródle przed filtrami i niezależnie
  od granic partii. Musi być znana dokładnie jedna działka.
- Identyczne wpisy są scalane z pominięciem technicznego `gid`, bbox i adresu
  usługi. Różne wersje lub sprzeczne wpisy tej samej transakcji są odrzucane;
  kod nie wybiera automatycznie „najnowszego” fragmentu transakcji.
- Zostają grunty niezabudowane, wolny rynek i potwierdzony pełny udział.
  Brak udziału, udziały częściowe, błędne lub wielokrotne wpisy są osobno
  liczone w raporcie. Ceny udziałów nie są mnożone przez odwrotność ułamka.
- Data musi mieścić się od 2015 roku do daty odcięcia włącznie.
  Cena musi być dodatnia i skończona. Jeśli podano także dodatnią cenę
  nieruchomości lub działki, musi odpowiadać cenie transakcji z tolerancją 1 gr.
  Ujemne i nieskończone ceny składowe są odrzucane; zero traktowane jest
  jako brak ceny składowej. Brak ceny składowej nie potwierdza sam w sobie
  kompletności transakcji — to ograniczenie dostępnego eksportu.
- Pole liczone jest tylko z poprawnej geometrii poligonowej w EPSG:2180.
  Geometria rozstrzyga, czy powierzchnia ewidencyjna jest w m² czy hektarach,
  z dotychczasową tolerancją 0,80–1,25. Brak/błędna powierzchnia ewidencyjna
  może być zastąpiona polem geometrii z oznaczeniem źródła. Rozbieżność obu
  wartości albo brak geometrii wyklucza rekord z tego zbioru.
- Zakres badania pozostaje 100–200 000 m². Nie ma progów ceny całkowitej,
  progów ceny za m² ani usuwania skrajnych percentyli. Statystyczne
  filtrowanie cen należy dopasować dopiero na zbiorze treningowym.

To ostrożny zbiór do dalszych prac, a nie gwarancja poprawności wszystkich
transakcji. Odrzucone rekordy nadal istnieją w surowym pliku. Zmiana zasad
nie wymaga ponownego pobierania danych.

## Pamięć i pliki

Pierwszy przebieg buduje tymczasowy indeks SQLite: klucze, podpisy wpisów
oraz informacje o składzie transakcji. Drugi przebieg czyta partie, filtruje
je i zapisuje bezpośrednio do Parquet. Nie przechowuje całego kraju w pandas.
SQLite służy tylko do obliczeń; nie zastępuje planowanej bazy PostGIS.

Indeks jest usuwany po zakończeniu i przy obsłużonym błędzie. Wynik pojawia
się dopiero po zakończeniu obu przebiegów. Nie powstają kopie etapów ani
pliki odrzuconych rekordów. Kontrola wolnego miejsca zostawia 10 GiB zapasu
oraz dodatkowy margines przed kolejną partią.

| Plik wyniku | Zawartość |
|---|---|
| `transakcje.parquet` | Oczyszczone transakcje, geometria i podstawowe wielkości |
| `raport_czyszczenia.csv` | Rozłączne powody odrzucenia, duplikaty i liczba zaakceptowanych |
| `rozklad_gruntow.csv` | Liczebności według województwa i sposobu użytkowania |
| `podsumowanie.json` | Parametry uruchomienia, liczebności, czas i rozmiar wyniku |

Suma wierszy raportu odpowiada liczbie wierszy surowych. Wynik zachowuje
kolumny źródłowe. `klucz_transakcji` identyfikuje transakcję globalnie,
`teryt_gmina` ma siedem cyfr (łącznie z typem gminy), a `teryt_obreb`
identyfikuje obręb. GeoParquet zachowuje CRS; stare bbox nie jest kopiowane.

## Kolejne etapy i stare wyniki

W `etl/cechy_osm/`, `etl/sasiedztwo_cenowe/` oraz `etl/uldk/` pozostaje kod
wcześniejszego eksperymentu. Wymaga dostosowania przed użyciem na całej Polsce.
`model/pierwszy.py`, `zobacz.py` i `do_excela.py` nadal czytają wcześniejszy
`db/dane/gotowe/dane_z_cechami.parquet`, którego nowe czyszczenie nie nadpisuje.
Nie są jeszcze podłączone do nowego zbioru.

Zostały do wykonania: cechy otoczenia, poprawne sąsiedztwo cenowe, PostGIS
oraz porównanie modeli. Zakres obejmuje RCN i OSM; bez GUS, powodzi, NMT,
dodatkowych danych planistycznych i BDOT10k. Opis cech: [praca/CECHY.md](praca/CECHY.md).
Pobieranie źródeł: [db/README.md](db/README.md). Prywatne notatki są w
`praca/prywatne/`, poza Git i obrazem Dockera.

## Testy

```bash
python -m unittest discover -s tests -v
```

Testy korzystają z małych sztucznych plików, bez sieci i bez krajowych danych.
Sprawdzają skład transakcji między partiami, klucze, wersje, udziały, ceny,
daty, geometrię, niezależność od przyszłych transakcji i ochronę plików.
