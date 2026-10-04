# Predykcja cen działek — przygotowanie danych

Bieżący etap czyści krajowy Rejestr Cen Nieruchomości partiami. Zapisuje
jeden GeoParquet z transakcjami i flagami jakości oraz małe raporty.
Odrzuca nieznane udziały, zachowuje braki geometrii i korzysta z zapisanego
cache ULDK i opcjonalnie pobiera pełne granice. Nie liczy jeszcze OSM,
sąsiedztwa cenowego ani modeli.

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

Wynik uwzględnia pełne i częściowe, jednoznacznie zapisane udziały.
Braki geometrii pozostają do uzupełnienia. Do dalszego przygotowania modeli
służy filtr `do_modelu`. Nie pobrano jeszcze wszystkich brakujących granic.

Przeliczenie z 03.10.2026 po zmianie zasad udziałów: **802 857** rekordów,
w tym **525 478** z `do_modelu = true` i **277 379** do uzupełnienia lub
weryfikacji. Odrzucono 136 968 rekordów z nieznanym lub błędnym udziałem.
Zachowano 51 826 udziałów częściowych; 36 514 spełnia warunki modelowania.
Dolny Śląsk: 62 401 rekordów. Plik ma 150 526 942 bajty.
Nie wykonano nowych zapytań ULDK. Poprzedni wynik pozostaje w
`db/dane/gotowe/polska_oczyszczone_przed_filtrem_udzialow/`.

Uruchomienie nie wymaga opcji z `--`. Ustawienia zmieniamy w `config.py`:
`WOJEWODZTWO = None` oznacza Polskę, a `"02"` Dolny Śląsk.
`LIMIT_ULDK = 0` używa tylko cache; większa liczba ogranicza nowe zapytania.
Ścieżki, datę odcięcia i wielkość partii ustawiamy w tym samym pliku.
`main.py` wywołuje etapy kolejno: czyszczenie RCN, pobranie brakujących
granic i przeliczenie po ULDK. Istniejący oczyszczony wynik jest używany
ponownie. Żeby zmienić filtry i przeliczyć źródło, ustaw nową `SCIEZKA_OCZYSZCZONE`.
`UZUPELNIJ_ULDK = False` wyłącza dwa ostatnie etapy — obecnie pobieranie
działa już osobno. Włączenie wymaga ustawienia `True`, gdy nie działa druga
kopia pobierania. OSM i trening nie są jeszcze podłączone do krajowego przepływu.

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
- Zostają grunty niezabudowane i wolny rynek. Zachowujemy pełny udział
  oraz pojedynczy udział częściowy z zakresu (0, 1]. Brak, błędny zapis
  i wiele wpisów udziałów powodują odrzucenie rekordu. Puste pole nie oznacza 1/1.
  `udzial_sprzedany` przechowuje ułamek jako liczbę, a oryginalny zapis pozostaje
  w `nier_udzial`. Cena za m² to `tran_cena_brutto / (powierzchnia_m2 * udzial_sprzedany)`.
  `cena_przeliczona_z_udzialu` oznacza udział częściowy. To proporcjonalne
  przeliczenie, nie potwierdzona cena sprzedaży całej nieruchomości; przy
  modelowaniu trzeba porównać jakość z wariantem korzystającym tylko z pełnych udziałów.
  Źródłowa cena transakcji i powierzchnia całej działki nie są zmieniane.
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
  wartości albo brak geometrii pozostawia rekord z pustą powierzchnią
  i oznaczeniem do wyjaśnienia. Nie zgadujemy jednostki.
- Zakres modelowania pozostaje 100–200 000 m². Rekordy poza nim także
  zostają w pliku, ale mają `do_modelu = false`. Nie ma progów ceny całkowitej,
  progów ceny za m² ani usuwania skrajnych percentyli. Statystyczne
  filtrowanie cen należy dopasować dopiero na zbiorze treningowym.

`do_modelu` wymaga znanego udziału, zweryfikowanej powierzchni w zakresie
oraz poprawnej ceny za m². To gotowość danych podstawowych, nie dowód pełnej
poprawności transakcji. `status_jakosci` i `powody_wstrzymania` wyjaśniają
braki. `ma_srodek` wskazuje, czy można liczyć odległości. Brak zweryfikowanej
powierzchni daje puste `cena_m2`, nie zero ani zgadywaną cenę.

Pozostałe filtry struktury transakcji, dat i cen działają jak wcześniej.
Odrzucone przez nie rekordy nadal są w surowym pliku.

## ULDK: środki i pełne granice

Najpierw używana jest poprawna geometria RCN. Gdy jej brakuje, program
sprawdza cache pełnych granic `db/dane/posrednie/uldk_granice.sqlite`.
Następnie do brakujących współrzędnych dobiera istniejące środki z
`uldk_srodki.parquet`. Stary plik ze środkami nie jest zmieniany.

Środek wystarcza do odległości, ale nie potwierdza pola ani kształtu.
Pełne granice ULDK są używane przed ustaleniem powierzchni i gotowości
rekordu. `zrodlo_geometrii`, `zrodlo_srodka` i `uldk_pobrano_utc` pokazują
pochodzenie danych. ULDK zwraca bieżącą geometrię — nie zakładamy, że
odpowiada ona granicom z daty historycznej sprzedaży.

Przykład stopniowego uzupełniania (maksymalnie 1000 nowych zapytań):

```bash
# W config.py: LIMIT_ULDK = 1000 oraz nowa SCIEZKA_OCZYSZCZONE
python main.py
```

Limit jest wspólny dla całego uruchomienia. Każda odpowiedź jest zapisywana
od razu, a kolejne uruchomienie pomija już pobrane granice. Błędy i brak
wyniku mogą być ponownie sprawdzone po dobie; nie oznaczają trwałego
nieistnienia działki. Stare puste środki nie blokują pobierania granic.
W nowym pliku pojawi się całość transakcji z uwzględnieniem aktualnego cache.

Zapytania mają jawne EPSG:2180; sprawdzamy zwrócony identyfikator i geometrię.
Format opisuje [dokumentacja ULDK](https://uldk.gugik.gov.pl/opis.html).

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
| `raport_czyszczenia.csv` | Rozłączne powody odrzucenia, duplikaty i liczba zachowanych |
| `rozklad_gruntow.csv` | Liczebności według województwa, użytkowania i flagi `do_modelu` |
| `podsumowanie.json` | Parametry, liczebności i jakość, źródła środków, zapytania ULDK, czas i rozmiar |

Suma wierszy raportu odpowiada liczbie wierszy surowych. Wynik zachowuje
kolumny źródłowe. `klucz_transakcji` identyfikuje transakcję globalnie,
`teryt_gmina` ma siedem cyfr (łącznie z typem gminy), a `teryt_obreb`
identyfikuje obręb. GeoParquet zachowuje CRS; stare bbox nie jest kopiowane.

## Kolejne etapy i stare wyniki

W `etl/cechy_osm/` i `etl/sasiedztwo_cenowe/` pozostaje kod wcześniejszego
eksperymentu. Wymaga dostosowania przed użyciem na całej Polsce.
ULDK jest już podłączone do nowego czyszczenia.
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
Testy ULDK obejmują ponowne użycie cache, limit zapytań, błędy usługi,
weryfikację identyfikatora i CRS oraz rozróżnienie środka od granic.

## Uzupełnienie brakujących granic w całym zbiorze

`python -m etl.uldk.uzupelnij` zbiera unikalne identyfikatory działek bez
geometrii z aktualnego wyniku i pobiera ich granice kolejno do cache SQLite.
Po zakończeniu automatycznie przelicza źródłowy RCN do
`db/dane/gotowe/polska_po_uldk/`, pozostawiając poprzedni wynik.
Postęp zapisuje w `db/dane/posrednie/uldk_postep.json` co 20 działek.
Ponowne uruchomienie korzysta z pobranych granic. Błędy mogą być ponowione
po dobie. Dwadzieścia kolejnych błędów sieci zatrzymuje proces.
Komputer musi działać z dostępem do internetu; uśpienie wstrzymuje pracę.

Podgląd trwającego pobierania w drugim terminalu:

```bash
.venv312/bin/python postep.py
```

Pokazuje liczbę sprawdzonych działek, pozostałe, znalezione granice i czas
pozostały do końca pobierania. Szacunek powstaje z tempa od otwarcia podglądu,
po pierwszych nowych wynikach. Zakończenie podglądu przez Ctrl+C nie zatrzymuje
pobierania. Po pobraniu następuje osobne przeliczenie RCN (dotąd około 6 minut).

## Paczki powiatowe EGiB

Dla masowego uzupełniania granic używamy teraz `python -m etl.egib.paczki`.
Skrypt korzysta z cache ULDK, pobiera jedną paczkę powiatową ZIP/GPKG naraz,
czyta partiami tylko warstwę działek i zapisuje potrzebne geometrie oraz pola.
Po zatwierdzeniu cache usuwa nowe pliki robocze powiatu. Zachowuje 10 GiB zapasu.
Adresy pochodzą z [oficjalnej wtyczki GUGiK](https://github.com/GlownyUrzadGeodezjiIKartografii/pobierz_dane_GUGiK/blob/main/pobierz_dane_GUGiK_dockwidget.py).

Cache `granice_egib` i wykaz `paczki_egib` są w lokalnym SQLite obok tabeli ULDK.
Wykaz zawiera URL, datę pobrania, SHA256, rozmiar i liczebności. Baza EGiB ma
osobne oznaczenie źródła w wyniku; aktualna geometria nie potwierdza historycznych granic.
Nieznalezione identyfikatory pozostają brakami. Rozbieżności powierzchni nadal blokują modelowanie.

Po pobraniu powstanie `db/dane/gotowe/polska_po_egib/`; stary wynik zostaje.
`python postep.py` automatycznie pokazuje postęp EGiB, gdy istnieje jego plik postępu.
Log: `db/dane/posrednie/egib_pobieranie.log`. Przerwane pobieranie wznawia ta sama komenda.
Gotowe powiaty są pomijane; przerwany plik bez walidatora wersji jest pobierany od początku.
Nie uruchamiaj drugiego pobierania równolegle. `UZUPELNIJ_EGIB` w config.py pozwala
uruchomić ten etap również z main.py; teraz jest False, bo proces działa osobno.

## Krajowe cechy OSM

`python -m etl.cechy_osm.polska` najpierw buduje warstwy z krajowego PBF,
a potem liczy 27 cech dla rekordów `do_modelu=true` z `polska_po_egib`.
Wynik: `db/dane/gotowe/polska_cechy_osm/transakcje.parquet` i podsumowanie.
`LICZ_OSM` w config.py włącza ten etap również w main.py; jest wyłączone,
gdy obliczenia uruchomiono osobno. `python postep.py` pokazuje postęp.

Warstwy czytane są strumieniowo przez pyosmium, z tymczasowym indeksem
współrzędnych na dysku. Cache warstw to Parquet w `posrednie/osm_polska`.
Podczas liczenia w pamięci jest jedna warstwa i tabela cech. Nie dzielimy
sąsiadów według województw. Obiekty poza ekstraktem Polski mogą być pominięte.

Odległości do dróg, budynków, wody i usług liczone są do geometrii,
od środka działki, w metrach EPSG:2180. Liczby budynków i POI opierają się
na centroidach obiektów. Udziały lasu i zabudowy liczą sumę geometryczną
przecięć z buforem 500 m, bez podwajania nakładających się powierzchni.
Drogi utwardzone wymagają jawnego tagu surface; klasa highway nie wystarcza.
Populacja miast pochodzi tylko z OSM; brak liczby nie jest zerem.
Miejscowości reprezentują punkty place; obszary i punkty szkół/sklepów
są uwzględniane. POI oznacza liczbę zapisanych obiektów OSM, nie zweryfikowaną
liczbę placówek (punkt i obszar mogą opisywać to samo miejsce).

Puste warstwy dają braki, a nie fałszywe zera. OSM opisuje stan z daty
pobranego ekstraktu, nie historyczne otoczenie każdej transakcji. Odległość
do drogi nie potwierdza prawnego dostępu. Wagi z dawnych notatek nie są
zweryfikowanymi wynikami modeli. SQLite nadal służy jako cache granic;
docelowy PostgreSQL/PostGIS nie został jeszcze wdrożony.
