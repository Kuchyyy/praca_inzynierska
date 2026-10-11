# Dane i baza PostgreSQL/PostGIS

Są tu źródła, wyniki obliczeń i konfiguracja PostgreSQL/PostGIS w Dockerze.
Uruchomienie bazy: `docker compose up -d --build --wait db`.
Połączenie, trwały wolumen i kopie: [POSTGIS.md](POSTGIS.md).
Import danych do bazy jest osobnym etapem. Dane są lokalne, pomijane w Git
i w obrazie Dockera.

Źródła pobrane i sprawdzone 02.10.2026:

| Plik krajowy | Rozmiar | Sprawdzenie |
|---|---:|---|
| `0_transakcje_ceny_dzialki.parquet` | 1 165 042 946 B (1,17 GB) | 14 795 036 surowych wierszy, 29 kolumn, GeoParquet 1.1.0, EPSG:2180; odczyt próbek |
| `poland-260930.osm.pbf` | 2 102 684 575 B (2,10 GB) | Nagłówek OSM, stan z 30.09.2026 20:22:42 UTC; zgodne MD5 dostawcy |

Łącznie 3,27 GB (3,04 GiB). Liczba wierszy RCN dotyczy surowego
eksportu, a nie liczby transakcji po oczyszczeniu. Kontrola próbek
nie oznacza sprawdzenia jakości wszystkich rekordów.

```text
dane/
  surowe/rcn/     transakcje działek: Dolny Śląsk i Polska
  surowe/osm/     OSM Dolnego Śląska i Polski w PBF
  posrednie/     dotychczasowe pliki i cache ULDK/OSM
  gotowe/        stare cechy oraz polska_oczyszczone/ z nowym wynikiem
  zrodla.json    adresy, wersje, daty, rozmiary i sumy pobranych plików
```

## Pobranie Polski

Z głównego katalogu repo, w środowisku z zainstalowanym `pyarrow`:

```bash
python db/pobierz_dane.py
```

Skrypt pobiera kolejno krajowy GeoParquet RCN dotyczący działek oraz
OSM Polski z 30.09.2026. Nie pobiera wszystkich działek EGiB, lokali,
budynków RCN ani osobnych paczek wojewódzkich.

Adres RCN pochodzi z [oficjalnej wtyczki GUGiK](https://github.com/GlownyUrzadGeodezjiIKartografii/pobierz_dane_GUGiK/blob/main/pobierz_dane_GUGiK_dockwidget.py):
`run_geoparquet_download`, kod kraju `0`, typ `dzialki (RCN)`.
OSM pochodzi z [Geofabrik](https://download.geofabrik.de/europe/poland.html).
Przy dalszym wykorzystaniu danych należy zachować informację o źródle
i wymagane oznaczenie autorów OpenStreetMap.

Pliki trafiają najpierw do `.part`. Skrypt sprawdza rozmiar, odczytuje
metadane i małą próbkę Parquet lub nagłówek PBF, weryfikuje MD5 OSM
z Geofabrik i zapisuje SHA-256 obu plików. Dopiero potem nadaje nazwę końcową.
Geoportal nie udostępnił sumy kontrolnej w sprawdzonych nagłówkach;
lokalny SHA-256 pozwala wykryć późniejszą zmianę pliku, ale nie zastępuje
sumy opublikowanej przez dostawcę.

Wznowienie wymaga zgodnych metadanych i walidatora HTTP (ETag albo
Last-Modified). Bez niego częściowe pobranie zaczyna się od początku,
żeby nie połączyć dwóch wersji eksportu. Gotowe pliki nie są nadpisywane;
ponowne uruchomienie sprawdza je według lokalnego wykazu.
Sprawdzony eksport RCN nie podał ETag ani Last-Modified, więc po przerwaniu
trzeba pobrać go od początku. OSM udostępnia oba nagłówki.

## Miejsce na dysku

Skrypt sprawdza rozmiar przed każdym pobraniem i wolne miejsce podczas
zapisu. Zostawia minimum 10 GiB. Nie rozpakowuje PBF do XML ani nie
generuje krajowych warstw i plików pośrednich. Istniejące dane wojewódzkie
i cache pozostają na dysku, aby obecne uruchomienie nadal działało.

Krajowy RCN jest domyślnym wejściem `python main.py`. Czyszczenie czyta go
dwukrotnie partiami i używa usuwanego na końcu indeksu SQLite. Zapisuje
`gotowe/polska_oczyszczone/transakcje.parquet` i trzy małe raporty.
Nie tworzy kopii etapów ani plików odrzuconych rekordów.
Odrzuca nieznane udziały; dla znanych przelicza cenę przez powierzchnię i udział.
Zachowuje braki geometrii z flagą `do_modelu` oraz przyczyną wstrzymania.

Krajowy OSM pozostaje źródłem do następnego etapu. Czyszczenie nie czyta
PBF i nie liczy jeszcze cech otoczenia. Korzysta z cache środków ULDK,
a z ustawieniem `LIMIT_ULDK` w `config.py` także pobiera i zachowuje pełne granice
w `posrednie/uldk_granice.sqlite`. ULDK jest aktualnym źródłem geometrii,
nie archiwum granic z dat sprzedaży. Parametry,
zasady odrzucania danych i testy opisano w głównym [README](../../README.md).
