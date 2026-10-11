# Pełne cechy krajowe

Etap uruchamia `python -m etl.pozostale_cechy`. Czyta gotowy wynik OSM,
bez ponownego pobierania map i bez ograniczania danych do województwa.
Wynik zapisuje w `db/dane/gotowe/polska_pelne_cechy/`. Stare pliki pozostają.

## Cechy podstawowe i przeznaczenie

- `log_powierzchnia`: logarytm naturalny zweryfikowanej powierzchni.
- `miesiace_od_2015`: ciągły czas od stycznia 2015.
- `miejscowosc`: nazwa z segmentu MSC adresu RCN; brak pozostaje brakiem.
- `wskaznik_zwartosci`: 4π × pole geometrii / obwód².
- 24 wskaźniki kategorii przeznaczenia ze stałego słownika RCN, w tym wody morskie.
- `przezn_brak_danych` i `przezn_nieznana_kategoria`: osobne flagi.
- `ma_wpis_przeznaczenia`: obecność wpisu w RCN, również wpisu o braku planu/WZ.

Nie ma starej `ma_mpzp`, która błędnie utożsamiała informację w eksporcie
z istnieniem planu. WZ i użytkowanie gruntu nie są planem miejscowym.
Nie pobieramy dodatkowych źródeł planistycznych. Nieznany kod nie jest
zamieniany na znane przeznaczenie ani mylony z pustym polem.

## Podział czasowy i osiem cech cenowych

Domyślne `TEST_OD = "2025-01-01"`: wcześniejsze transakcje to trening,
od tej daty test. Podział dotyczy całych dni. Daty nie wybieramy na podstawie
wyników modelu. Wynik ma kolumnę `zbior`.

Każdy rekord może korzystać tylko z transakcji treningowych ze ściśle
wcześniejszego dnia. Wykluczamy też wcześniejsze sprzedaże tej samej działki.
Ceny testowe nie zasilają późniejszych rekordów testowych. Nie ograniczamy
sąsiedztwa do województwa ani powiatu; gmina i obręb ograniczają tylko
mediany grupowe i trend.

| Cecha | Definicja |
|---|---|
| `mediana_cena_m2_2km_ten_sam_uzytek` | Mediana w 2 km i ostatnich 24 miesiącach, identyczny niepusty kod użytkowania |
| `mediana_cena_m2_2km_24m` | Mediana w 2 km, ostatnie 24 miesiące |
| `mediana_cena_m2_5km_24m` | Mediana w 5 km, ostatnie 24 miesiące |
| `mediana_cena_m2_obreb` | Mediana wszystkich dopuszczalnych wcześniejszych sprzedaży w obrębie |
| `mediana_cena_m2_gmina` | Mediana wszystkich dopuszczalnych wcześniejszych sprzedaży w gminie |
| `liczba_transakcji_2km_24m` | Liczba sprzedaży w oknie 2 km i 24 miesięcy |
| `trend_cen_gmina_12m` | Mediana ostatnich 12 miesięcy / mediana wcześniejszych 12 miesięcy − 1 |
| `odl_najblizsza_transakcja_m` | Najbliższa dopuszczalna wcześniejsza sprzedaż, również dalej niż 5 km; bez limitu 24 miesięcy |

Okna miesięczne są kalendarzowe, dolna granica włączona, dzień wycenianej
transakcji wyłączony. Brak sąsiadów daje pustą medianę i odległość; licznik
wynosi zero. Trend wymaga przynajmniej jednej sprzedaży w każdym oknie;
przy małych próbach może być niestabilny. W danych występują też proporcjonalnie
przeliczone ceny udziałów — ich wpływ trzeba ocenić oddzielnie.

W późniejszych datach testowych zasób referencji nie jest aktualizowany
cenami testowymi. Dlatego część okien jest pusta. Nie uzupełniamy ich
przyszłymi cenami ani medianą obliczoną na całym zbiorze.

## Wejścia modelu

`cechy_modelu.json` podaje jawną listę kandydatów: 76 cech, w tym 7
kategorycznych. To 27 OSM + 10 istniejących RCN/lokalizacji + 31 nowych
podstawowych/przeznaczenia + 8 sąsiedztwa. Nie są to 76 niezależnych sygnałów:
część wskaźników jest powiązana lub stała. Ostateczny dobór następuje w treningu.

Cel to `cena_m2`. Ceny całkowite, VAT, identyfikatory, `zbior` i flagi jakości
nie należą do listy wejść. Rodzaj gruntu może być cechą albo podstawą osobnych
modeli. Kodowanie kategorii i imputację braków należy dopasować tylko na
treningu. Nie należy wybierać automatycznie wszystkich liczbowych kolumn.

Zmiana daty testu wymaga ponownego obliczenia sąsiedztwa. Walidacja na
wcześniejszych przedziałach czasu również wymaga przeliczenia cech dla
każdego podziału. To nie jest tabela przygotowana do losowego cross-validation.
Aktualne OSM i geometria EGiB nadal stanowią ograniczenie dla historycznej oceny.

`model/pierwszy.py` pozostaje historycznym eksperymentem; nie jest jeszcze
podłączony do nowego wyniku. Ten etap nie trenuje modeli ani nie tworzy PostGIS.
