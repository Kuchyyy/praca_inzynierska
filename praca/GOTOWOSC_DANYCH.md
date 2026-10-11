# Dane do treningu i wejścia aplikacji

Wynik źródłowy pozostaje w `db/dane/gotowe/polska_pelne_cechy/transakcje.parquet`.
Audyt i docelowy kontrakt są w `db/dane/gotowe/audyt_modelu/`. Nie trzeba
kopiować całego GeoParquet ani ponownie pobierać ULDK, EGiB lub OSM.

Uruchomienie z katalogu projektu:

```bash
.venv312/bin/python -m etl.audyt_danych
.venv312/bin/python -m etl.walidacja_modelu
```

`main.py` wykonuje te etapy przy `AUDYTUJ_DANE = True`. Ścieżki i daty
ustawiamy w `config.py`. Audyt wznawia profilowanie od ostatniej zapisanej
kolumny, jeżeli SHA256 danych, manifest, kod i ustawienia są zgodne.
Kontroluje zapas dysku i czyta cechy pojedynczo, partiami; w pamięci trzyma
jedynie wąską tabelę kontrolną oraz aktualną kolumnę, bez geometrii.
Nie usuwa transakcji ani nie zmienia źródła. Status `OK` oznacza przejście
kontroli spójności, nie ręczne potwierdzenie poprawności wszystkich cen.

## Wynik audytu

732 702 rekordy: trening 607 757, test 124 945. Wszystkie 16 województw.
Sprawdzane są klucze, podział czasowy, daty, ceny, zgodność ceny m²
z powierzchnią i udziałem, zakres powierzchni, współrzędne, nieskończoności,
nieujemność odległości/liczników i zakres udziałów/wskaźników.

- 46 910 transakcji dotyczy udziałów częściowych.
- 1501 cen leży poza percentylami 0,1%–99,9% wyznaczonymi na treningu:
  poniżej 0,10 lub powyżej 28 173,91 zł/m². To lista do przeglądu, nie dowód błędu.
- 8270 identyfikatorów działek występuje w treningu i teście. Podział czasowy
  pozostaje poprawny, ale wyniki trzeba też podać dla niewidzianych działek.
- `miejscowosc` ma 460 683 braki w treningu i 99 945 w teście; nie trafia do modelu.
- `przezn_nieznana_kategoria` jest stała na treningu; usunięto ją z wejść.

Pliki raportowe:

| Plik | Zawartość |
|---|---|
| `podsumowanie.json` | Status, błędy, liczebności i SHA256 danych |
| `profile.json` | Braki, kwantyle, liczba wartości, kategorie i nieznane kategorie testu |
| `pokrycie_wojewodztw.csv` | Rekordy według zbioru i województwa |
| `udzialy.csv` | Liczebności i mediany dla pełnych/częściowych udziałów |
| `ceny_do_przegladu.csv` | Klucze i dane kontrolne skrajnych cen |
| `dostepnosc_cech.csv` | Źródło i warunki uzyskania każdej z 76 cech |
| `cechy_modelu.json` | Docelowe wejścia, kategorie, zasady przetwarzania i warianty |

## Dwa warianty wejść

**Mapa (domyślny): 44 cechy.** Obejmuje geometrię, lokalizację administracyjną,
datę wyceny, OSM i siedem cech cenowych. Wyklucza sprzedającego, prawo,
użytkowanie, przeznaczenie RCN, miejscowość z historycznego adresu oraz medianę
wymagającą identycznego użytkowania.

Kliknięcie punktu wymaga najpierw rozpoznania identyfikatora działki i uzyskania
pełnej geometrii. Sam punkt nie wystarcza do pola i kształtu. Powierzchnię
trzeba weryfikować tak samo jak w ETL; nie zgadywać jednostki.

**Formularz: 74 cechy.** Rozszerza mapę o prawo, typ sprzedającego, użytkowanie,
przeznaczenie i medianę dla tego samego użytkowania. Wymaga jednoznacznego
mapowania odpowiedzi użytkownika na słownik RCN. Brak odpowiedzi pozostaje
brakiem, a brak informacji o planie nie oznacza braku planu. Wskaźniki
przeznaczenia należy tworzyć wspólnym słownikiem z
`etl/wczytanie_i_czyszczenie_cech/pozostale.py`.

Tabela dostępności opisuje warunki wdrożenia. Nie potwierdza, że działa już
API wyceny: do niego potrzebne są obsługa identyfikacji działki, geometria,
warstwy OSM, baza wcześniejszych transakcji oraz obliczanie cech pojedynczego
zapytania. Aktualne OSM i EGiB nie rekonstruują otoczenia historycznej sprzedaży.

## Trening i walidacja

- Dobór modelu: trening przed 2024-01-01, walidacja w 2024 roku.
- Ocena końcowa: trening przed 2025-01-01, test od 2025-01-01.
- Bez losowego dzielenia obecnej tabeli i bez dobierania parametrów na teście.

Gotowy zbiór rozwojowy zawiera 523 057 rekordów treningowych i 84 700
walidacyjnych. Test końcowy to osobne 124 945 rekordów.

`etl/walidacja_modelu.py` zapisuje w `walidacja/sasiedztwo.parquet` klucz,
zbiór oraz osiem cech przeliczonych wyłącznie z referencji sprzed 2024 roku.
Łączymy je po `klucz_transakcji` (`validate='one_to_one'`) z rekordami źródła
sprzed 2025 roku, zastępując dotychczasowe osiem cech i `zbior`.
Nie łączymy po numerze wiersza. Ceny walidacyjne nigdy nie trafiają do referencji.
Wynik końcowego treningu/testu nadal korzysta z oryginalnego sąsiedztwa.
Gotowa walidacja jest używana ponownie; przerwane obliczenie trzeba powtórzyć,
a zapis jest partiami i publikowany atomowo. Zmiana podziału wymaga nowego
katalogu audytu. Cache sprawdza dane i kod obliczeń.

`model/przygotowanie.py` udostępnia `przygotuj_wejscia` i
`zbuduj_przetwarzanie`. Pierwsza funkcja wybiera i porządkuje jawne kolumny,
sprawdza typy i odrzuca nieskończoności. Druga tworzy niedopasowany transformer:
mediana i wskaźniki braków dla liczb, skalowanie, stała `__BRAK__` i one-hot
z obsługą nieznanych kategorii. Całkiem pusta liczbowa kolumna treningowa
otrzymuje techniczne zero i wskaźnik braku; zero nie staje się obserwacją.
Brak całej wymaganej kolumny to błąd integracji.

Transformer należy umieścić w jednym sklearn Pipeline z modelem. `fit`
wykonujemy tylko na treningu danego podziału; walidacja, test i zapytanie
użytkownika korzystają z `transform`/`predict` bez ponownego dopasowania.
Zapisujemy cały dopasowany Pipeline, listę cech, wersje bibliotek i SHA256
źródła. Obecny etap nie dopasowuje jeszcze modelu ani imputacji.

Ceny skrajne zostają w danych. W treningu można porównać model ceny z modelem
logarytmu ceny, ale ocena końcowa powinna obejmować cały poprawny test.
Wariant pełnych udziałów porównujemy na tych samych rekordach testowych,
raportując też pełne i częściowe udziały osobno. Jeżeli referencje mają zawierać
wyłącznie pełne udziały, trzeba dodatkowo przeliczyć sąsiedztwo; samo usunięcie
częściowych udziałów z treningu tego nie zapewnia.

Historyczny `model/pierwszy.py` nie został przepięty: nadal jest wcześniejszym
eksperymentem. Nowy trening powinien używać kontraktu z katalogu audytu,
nie wybierać automatycznie wszystkich kolumn liczbowych.
