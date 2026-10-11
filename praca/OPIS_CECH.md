# Opis cech modelu — szczegółowo

Dokument opisuje każdą z 76 cech, z których korzysta model ceny działki: skąd pochodzi,
w którym pliku i funkcji powstaje, jak dokładnie jest liczona, po co jest w modelu
i jakie wartości przyjmuje w gotowym zbiorze.

Stan na 08.10.2026. Wszystkie liczby pochodzą z gotowego zbioru
`backend/db/dane/gotowe/polska_pelne_cechy/transakcje.parquet`
(SHA256 `b8b139e9…dcbfcc0d9`, sprawdzonego audytem ze statusem OK).

`CECHY.md` zostaje jako zapis wcześniejszych planów i rozważań. Ten dokument opisuje to,
co jest faktycznie policzone w kodzie.

---

## Spis treści

1. [W skrócie](#1-w-skrócie)
2. [Skąd biorą się transakcje](#2-skąd-biorą-się-transakcje)
3. [Cel modelu: cena za m²](#3-cel-modelu-cena-za-m)
4. [Jak czytać opisy cech](#4-jak-czytać-opisy-cech)
5. [Transakcja i prawo — 3 cechy](#5-transakcja-i-prawo--3-cechy)
6. [Lokalizacja administracyjna — 4 cechy](#6-lokalizacja-administracyjna--4-cechy)
7. [Położenie i kształt działki — 5 cech](#7-położenie-i-kształt-działki--5-cech)
8. [Czas — 2 cechy](#8-czas--2-cechy)
9. [Otoczenie z OpenStreetMap — 27 cech](#9-otoczenie-z-openstreetmap--27-cech)
10. [Przeznaczenie z RCN — 27 cech](#10-przeznaczenie-z-rcn--27-cech)
11. [Sąsiedztwo cenowe — 8 cech](#11-sąsiedztwo-cenowe--8-cech)
12. [Co trafia do modelu: warianty „mapa” i „formularz”](#12-co-trafia-do-modelu-warianty-mapa-i-formularz)
13. [Ograniczenia i ryzyka](#13-ograniczenia-i-ryzyka)
14. [Ranking siły związku z ceną](#14-ranking-siły-związku-z-ceną)

---

## 1. W skrócie

- **732 702 transakcje** sprzedaży niezabudowanych działek z całej Polski (16 województw),
  od 01.01.2015 do 25.09.2026.
- **Podział czasowy:** trening to sprzedaże przed 01.01.2025 (607 757), test to sprzedaże
  od 01.01.2025 (124 945). Do doboru modelu trening jest dodatkowo dzielony na
  część przed 2024 rokiem (523 057) i walidację z 2024 roku (84 700).
- **Cel:** `cena_m2`, czyli cena za metr kwadratowy całej działki.
- **76 kandydatów na wejścia** w 7 grupach:

| Grupa | Cechy | Typ | Gdzie powstaje | Źródło danych |
|---|---:|---|---|---|
| Transakcja i prawo | 3 | kategorie | czyszczenie RCN | RCN (rejestr cen nieruchomości) |
| Lokalizacja administracyjna | 4 | kategorie | czyszczenie RCN, pozostałe cechy | identyfikator działki, adres RCN |
| Położenie i kształt | 5 | liczby | geometria, pozostałe cechy | granice z RCN, EGiB lub ULDK |
| Czas | 2 | liczby | czyszczenie RCN, pozostałe cechy | data aktu notarialnego |
| Otoczenie z OSM | 27 | liczby i flagi 0/1 | cechy OSM | OpenStreetMap, ekstrakt Polski z 30.09.2026 |
| Przeznaczenie | 27 | flagi 0/1 | pozostałe cechy | pole przeznaczenia w RCN |
| Sąsiedztwo cenowe | 8 | liczby | sąsiedztwo cenowe | wcześniejsze ceny z RCN |
| **Razem** | **76** | 7 kategorii, 69 liczb | | |

- **Do modelu trafia 74 albo 44 cechy**, zależnie od wariantu (rozdział 12).
  Z obu wariantów wypada `miejscowosc` (za dużo braków) i `przezn_nieznana_kategoria`
  (stała równa 0).

---

## 2. Skąd biorą się transakcje

Cechy liczy pięć etapów. Każdy zapisuje wynik w osobnym katalogu
`backend/db/dane/gotowe/`, a kolejny czyta wynik poprzedniego. Kolejność wywołań pokazuje
[`backend/main.py`](../backend/main.py), ustawienia są w [`backend/config.py`](../backend/config.py).

```
surowy RCN (14 795 036 wierszy)
  │  1. czyszczenie RCN        → polska_oczyszczone/
  │  2. granice EGiB i ULDK    → polska_po_egib/         802 857 transakcji, 732 702 do modelu
  │  3. cechy OSM              → polska_cechy_osm/       + 27 cech
  │  4. pozostałe i sąsiedztwo → polska_pelne_cechy/     + 39 cech, manifest 76 cech
  │  5. audyt i walidacja      → audyt_modelu/           profil cech, warianty wejść
```

### 2.1. Czyszczenie RCN

Pliki: [`wczytywanie.py`](../backend/etl/wczytanie_i_czyszczenie_cech/wczytywanie.py)
(`oczysc_plik`), [`transakcje.py`](../backend/etl/wczytanie_i_czyszczenie_cech/transakcje.py)
(`zbuduj_indeks`, `podsumuj_indeks`) i
[`czyszczenie.py`](../backend/etl/wczytanie_i_czyszczenie_cech/czyszczenie.py) (`wyczysc_partie`).

Plik RCN ma jeden wiersz na działkę w transakcji. Najpierw cały plik trafia do indeksu
SQLite, żeby sprawdzić skład każdej transakcji, nawet gdy jej działki leżą w różnych
partiach. Potem dane są czyszczone partiami po 25 000 wierszy. Każdy odrzucony wiersz
ma zapisany powód, a raport musi się bilansować z liczbą wierszy surowych.

| Powód odrzucenia | Wiersze | Dlaczego |
|---|---:|---|
| brak klucza transakcji | 1 392 287 | bez przestrzeni nazw i identyfikatora nie da się złożyć transakcji |
| transakcja wielodziałkowa | 8 017 067 | cena dotyczy kilku działek naraz, nie da się jej przypisać jednej |
| niepełny skład transakcji | 202 077 | brak identyfikatora którejś działki |
| sprzeczne wpisy transakcji | 195 732 | te same klucze z różną treścią |
| różne wersje transakcji | 209 | kilka wersji bez historii zmian |
| powtórzone wiersze | 18 751 | dokładne duplikaty |
| błędny identyfikator działki | 9 905 | identyfikator nie pasuje do wzorca TERYT |
| brak daty | 74 942 | nie da się umieścić w czasie |
| data z przyszłości | 103 | po dacie odcięcia `DATA_DO = 2026-10-02` |
| data przed 2015 | 1 648 965 | poza zakresem badania (`ROK_OD = 2015`) |
| inny rodzaj nieruchomości | 2 159 068 | zostają tylko `nieruchomoscGruntowaNiezabudowana` |
| inny rodzaj transakcji | 113 639 | zostaje tylko `wolnyRynek` |
| brak lub błędna cena | 2 014 | cena pusta, zerowa lub ujemna |
| niezgodne ceny składowe | 20 452 | cena nieruchomości lub działki różni się od ceny transakcji |
| nieznany lub błędny udział | 136 968 | bez znanego udziału nie da się przeliczyć ceny na całą działkę |
| **zachowane** | **802 857** | |

Przy okazji czyszczenia powstają cechy `teryt_*`, `rok`, `udzial_sprzedany` i flagi jakości.

### 2.2. Granice działek i powierzchnia

Pliki: [`geometria.py`](../backend/etl/wczytanie_i_czyszczenie_cech/geometria.py)
(`dodaj_geometrie`, `ustal_powierzchnie`), [`egib/paczki.py`](../backend/etl/egib/paczki.py)
(`uzupelnij_egib`, `wybierz_granice`), [`uldk/granice.py`](../backend/etl/uldk/granice.py)
i [`uldk/srodki.py`](../backend/etl/uldk/srodki.py).

Granica działki pochodzi z pierwszego dostępnego źródła:

| Źródło granicy | Transakcje (z 802 857) |
|---|---:|
| geometria zapisana w RCN | 542 493 |
| paczka powiatowa EGiB (GUGiK) | 152 196 |
| ULDK (usługa GUGiK, zapytanie po identyfikatorze) | 61 043 |
| brak granicy | 47 125 |

Poligon musi być poprawny, niepusty, w układzie EPSG:2180 i mieć dodatnie pole.
Z poligonu liczone są `pole_geom_m2`, `obwod_m` i środek (`x_2180`, `y_2180`).

Powierzchnia z ewidencji w RCN miesza hektary i metry bez oznaczenia. Funkcja
`ustal_powierzchnie` porównuje ją z polem policzonym z granic:

- stosunek ewidencja / pole w przedziale 0,80–1,25 → ewidencja w m² (361 960 transakcji),
- ten sam stosunek po pomnożeniu ewidencji przez 10 000 → ewidencja w hektarach (388 635),
- brak powierzchni w ewidencji → pole z geometrii (64),
- żadne z powyższych → rozbieżność, powierzchnia pusta (5 073),
- brak granicy → nie da się sprawdzić (47 125).

Transakcja trafia do modelu (`do_modelu = True`), gdy ma sprawdzoną powierzchnię
w zakresie 100–200 000 m² i poprawną cenę za m². Odpadło 17 075 działek poniżej 100 m²
i 882 powyżej 200 000 m². **Do modelu trafiają 732 702 transakcje.**

### 2.3. Otoczenie z OSM

Pliki: [`cechy_osm/warstwy.py`](../backend/etl/cechy_osm/warstwy.py)
(`przygotuj_warstwy`, `wybierz_warstwy`) i
[`cechy_osm/polska.py`](../backend/etl/cechy_osm/polska.py) (`policz_osm`,
`odleglosci_do_geometrii`, `pokrycie`). Szczegóły w rozdziale 9.

Plik [`cechy_osm/odleglosci.py`](../backend/etl/cechy_osm/odleglosci.py) to starsza wersja
dla jednego województwa (pyrosm). Nie bierze udziału w obecnym, krajowym przepływie.

### 2.4. Pozostałe cechy i sąsiedztwo cenowe

Pliki: [`pozostale_cechy.py`](../backend/etl/pozostale_cechy.py) (`przygotuj_pozostale`),
[`wczytanie_i_czyszczenie_cech/pozostale.py`](../backend/etl/wczytanie_i_czyszczenie_cech/pozostale.py)
(`dodaj_pozostale`) i [`sasiedztwo_cenowe/polska.py`](../backend/etl/sasiedztwo_cenowe/polska.py)
(`dodaj_sasiedztwo`). Ten etap dodaje 4 cechy podstawowe, 27 cech przeznaczenia i 8 cech
sąsiedztwa, wyznacza podział na trening i test (kolumna `zbior`) i zapisuje jawną listę
wejść `cechy_modelu.json`.

Plik [`sasiedztwo_cenowe/ceny.py`](../backend/etl/sasiedztwo_cenowe/ceny.py) to starsza
wersja z etapu jednego województwa i nie jest używana.

### 2.5. Audyt i walidacja

Pliki: [`audyt_danych.py`](../backend/etl/audyt_danych.py) (`audytuj_dane`,
`dostepnosc_cech`, `profil_kolumny`), [`walidacja_modelu.py`](../backend/etl/walidacja_modelu.py)
i [`model/przygotowanie.py`](../backend/model/przygotowanie.py). Audyt sprawdza spójność
(klucze, daty, wzór ceny, zakresy, nieskończoności), profiluje każdą cechę osobno dla
treningu i testu, dzieli cechy na warianty wejść i zapisuje kontrakt modelu
w `audyt_modelu/cechy_modelu.json`.

---

## 3. Cel modelu: cena za m²

**Kod:** `cena_m2`. **Gdzie:** `czyszczenie.py`, `wyczysc_partie`.

```
cena_m2 = tran_cena_brutto / (powierzchnia_m2 × udzial_sprzedany)
```

- `tran_cena_brutto` to cena całej transakcji z RCN (transakcja ma dokładnie jedną działkę).
- `udzial_sprzedany` to sprzedany udział jako ułamek, np. `1/2` → 0,5. Przy sprzedaży
  części cena jest przeliczana proporcjonalnie na całą działkę. Takich transakcji jest
  46 910 (6,4%).
- Audyt sprawdza wzór dla każdego wiersza z tolerancją 1e−8.

| Zbiór | Transakcje | 1. kwartyl | Mediana | 3. kwartyl |
|---|---:|---:|---:|---:|
| trening | 607 757 | 7,69 zł/m² | 40,00 zł/m² | 100,00 zł/m² |
| test | 124 945 | 9,18 zł/m² | 52,97 zł/m² | 136,72 zł/m² |

Mediana dla pełnych udziałów to 39,80 zł/m² w treningu i 52,44 zł/m² w teście, a dla
częściowych 63,33 i 61,52 zł/m². Rozkład jest silnie prawoskośny, więc warto porównać
model ceny z modelem jej logarytmu.

**Wartości skrajne.** 1 501 cen leży poza przedziałem 0,10–28 173,91 zł/m²
(percentyle 0,1% i 99,9% treningu). Maksimum to 64 266 877 479 zł/m²: tak wychodzi przy
udziale rzędu 2·10⁻¹¹, gdy cena zapisana w RCN dotyczy w praktyce większej części
nieruchomości. Udział poniżej 0,001 ma 1 061 transakcji. Te ceny zostają w danych, ale
trafiają na listę `audyt_modelu/ceny_do_przegladu.csv`.

---

## 4. Jak czytać opisy cech

Każda cecha ma ten sam układ:

- **Kod** — nazwa kolumny w danych i w `cechy_modelu.json`.
- **Gdzie** — plik i funkcja, które ją liczą.
- **Jak** — dokładny sposób liczenia, z parametrami z kodu.
- **Po co** — co ma uchwycić w cenie.
- **Wartości** — liczone na wszystkich 732 702 transakcjach: minimum, 1. kwartyl (p25),
  mediana, 3. kwartyl (p75), percentyl 99 (p99) i maksimum. Braki podane osobno dla
  treningu (T) i testu (S).
- **Związek z ceną** — współczynnik korelacji rang Spearmana ρ z `cena_m2` na treningu.
  ρ bliskie +1 oznacza, że im większa cecha, tym wyższa cena. ρ bliskie −1 oznacza
  odwrotną zależność, a ρ blisko 0 brak zależności monotonicznej. Model drzewiasty może
  jednak wykorzystać zależność niemonotoniczną albo zależność widoczną dopiero razem
  z inną cechą. ρ nie jest więc ważnością cechy w modelu. Dla flag 0/1 i kategorii
  podana jest też mediana ceny w każdej grupie.
- **Przy wycenie** — skąd wziąć wartość dla nowej działki w panelu.

Odległości są euklidesowe, w metrach, w układzie EPSG:2180, liczone od **środka
(centroidu) działki**. Gdy środek leży wewnątrz obiektu (np. budynku), odległość wynosi 0.

---

## 5. Transakcja i prawo — 3 cechy

### `tran_sprzedajacy` — kto sprzedaje

- **Gdzie:** kolumna RCN `tran_sprzedajacy`, przenoszona bez zmian przez czyszczenie.
- **Jak:** kategoria ze słownika RCN. Kodowanie one-hot i stała `__BRAK__` dla braków
  dopiero na treningu (`model/przygotowanie.py`, `zbuduj_przetwarzanie`).
- **Po co:** sprzedaż przez firmę, gminę albo Skarb Państwa to inny rynek niż sprzedaż
  między osobami fizycznymi: przetargi, działki inwestycyjne, grunty rolne z zasobu państwa.
- **Wartości (trening):**

| Kategoria | Transakcje | Mediana ceny |
|---|---:|---:|
| `osobaFizyczna` | 564 361 | 38,57 zł/m² |
| `osobaPrawna` | 33 475 | 107,56 zł/m² |
| `jednostkaSamorzaduTerytorialnego` | 7 124 | 50,62 zł/m² |
| `skarbPanstwa` | 2 773 | 5,54 zł/m² |

  Braki: T 24, S 0. Test nie ma kategorii nieznanych z treningu.
- **Przy wycenie:** formularz, 4 opcje (osoba fizyczna, firma, gmina, Skarb Państwa).

### `nier_prawo` — prawo do gruntu

- **Gdzie:** kolumna RCN `nier_prawo`, bez zmian.
- **Jak:** kategoria, kodowana jak wyżej.
- **Po co:** użytkowanie wieczyste i własność mają inną wartość. Użytkowanie wieczyste
  występuje głównie w miastach, stąd wysoka mediana.
- **Wartości (trening):**

| Kategoria | Transakcje | Mediana ceny |
|---|---:|---:|
| `wlasnoscNieruchomosciGruntowej` | 594 917 | 39,98 zł/m² |
| `uzytkowanieWieczyste` | 7 275 | 100,53 zł/m² |
| `wlasnoscBudynkuWrazZPrawemZwiazanym` | 3 239 | 130,00 zł/m² |
| `wlasnoscLokaluWrazZPrawemZwiazanym` | 517 | 155,56 zł/m² |

  Braki: T 1 809, S 0. Dwie ostatnie kategorie (3 756 transakcji) to niespójność RCN:
  transakcja jest opisana jako sprzedaż niezabudowanego gruntu, a prawo jako własność
  budynku lub lokalu.
- **Przy wycenie:** formularz, 2 opcje: własność albo użytkowanie wieczyste.

### `dzi_sposob_uzyt` — sposób użytkowania (rodzaj gruntu)

- **Gdzie:** kolumna RCN `dzi_sposob_uzyt`, bez zmian.
- **Jak:** kategoria. Ta sama kolumna wyznacza „ten sam użytek” w cesze
  `mediana_cena_m2_2km_ten_sam_uzytek` i może służyć do podziału na osobne modele
  (tak robi `model/pierwszy.py`).
- **Po co:** to najsilniejszy podział rynku. Mediany różnią się 14-krotnie między gruntami
  leśnymi a komunikacyjnymi.
- **Wartości (trening):**

| Kategoria | Transakcje | Mediana ceny |
|---|---:|---:|
| `gruntyRolne` | 415 166 | 30,00 zł/m² |
| `inne` | 95 982 | 60,00 zł/m² |
| `gruntyZabudowaneIZurbanizowane` | 77 104 | 77,49 zł/m² |
| `gruntyLesne` | 10 529 | 6,40 zł/m² |
| `terenyKomunikacyjne` | 3 920 | 90,00 zł/m² |

  Braki: T 5 056, S 184.
- **Przy wycenie:** formularz. Paczki EGiB są dziś używane tylko do granic, więc rodzaj
  gruntu wybiera użytkownik.

---

## 6. Lokalizacja administracyjna — 4 cechy

Kody TERYT są wycinane z identyfikatora działki `dzi_id_dzialki` w `wyczysc_partie`
wyrażeniem `^(\d{2})(\d{2})(\d{2})_([1-9])\.(\d{4})\.(\S+)$`, np.
`121901_2.0007.1432/2` → województwo `12`, powiat `1219`, gmina `1219012`
(z cyfrą rodzaju gminy), obręb `121901_2.0007`, numer `1432/2`.
Identyfikator z błędnym kodem województwa odrzuca czyszczenie (9 905 wierszy).

### `teryt_woj` — województwo

- **Jak:** pierwsze dwie cyfry identyfikatora. 16 wartości, bez braków.
- **Po co:** najszerszy poziom różnic regionalnych.
- **Wartości (trening, 8 największych):**

| Kod | Transakcje | Mediana ceny |
|---|---:|---:|
| 30 (wielkopolskie) | 79 265 | 52,14 zł/m² |
| 12 (małopolskie) | 68 424 | 40,97 zł/m² |
| 22 (pomorskie) | 53 977 | 67,46 zł/m² |
| 24 (śląskie) | 53 172 | 70,00 zł/m² |
| 02 (dolnośląskie) | 50 433 | 45,00 zł/m² |
| 14 (mazowieckie) | 48 908 | 65,14 zł/m² |
| 04 (kujawsko-pomorskie) | 37 520 | 45,83 zł/m² |
| 06 (lubelskie) | 33 924 | 6,71 zł/m² |

- **Przy wycenie:** z identyfikatora działki (wariant „mapa” i „formularz”).

### `teryt_powiat` — powiat

- **Jak:** pierwsze cztery cyfry. 311 powiatów w treningu, bez braków.
- **Po co:** różnice między powiatem podmiejskim a peryferyjnym w tym samym województwie.
- **Wartości:** najwięcej transakcji ma powiat `2205` (21 716, mediana 64,81 zł/m²),
  potem `3021` (13 517; 150,00), `1206` (12 421; 73,33), `0403` (11 081; 67,74),
  `0223` (9 514; 102,04) i `1261` (9 377; 280,56). W teście 329 transakcji jest
  z powiatów, których nie ma w treningu. One-hot przypisze im same zera.
- **Przy wycenie:** z identyfikatora działki.

### `teryt_gmina` — gmina

- **Jak:** sześć cyfr i cyfra rodzaju gminy (7 znaków). 2 538 gmin w treningu, bez braków.
- **Po co:** najdokładniejszy podział administracyjny używany wprost przez model.
- **Wartości:** największa gmina w treningu to `2205085` (6 950 transakcji, mediana
  120,00 zł/m²), dalej `1261049` (5 321; 324,32) i `2261011` (3 554; 298,27).
  W teście 539 transakcji pochodzi z gmin nieobecnych w treningu.
- **Uwaga:** przy 2 538 kategoriach one-hot daje bardzo szeroką macierz. Dla modeli
  liniowych warto rozważyć kodowanie zbiorcze. Medianę ceny w gminie i tak niesie
  cecha `mediana_cena_m2_gmina`.
- **Przy wycenie:** z identyfikatora działki.

### `miejscowosc` — miejscowość z adresu

- **Gdzie:** `pozostale.py`, `dodaj_pozostale`.
- **Jak:** z adresu RCN `dzi_adres` (format `MSC:…;UL:…;NR_PORZ:…`) wycinany jest segment
  `MSC:` wyrażeniem `(?:^|;)\s*MSC:([^;]+)`, przycinany i zamieniany na wielkie litery.
  Pusty napis staje się brakiem.
- **Po co:** w jednej gminie miejscowości mogą się różnić cenami kilkukrotnie.
- **Wartości:** 8 814 nazw w treningu. Braki: T 460 683 (75,8%), S 99 945 (80,0%).
  Najczęstsze: KRAKÓW (4 636, mediana 307,69 zł/m²), WARSZAWA (2 516; 630,67),
  BIAŁYSTOK (1 922; 250,63), CZĘSTOCHOWA (1 642; 120,00), LUBLIN (1 639; 232,92).
- **Decyzja:** **nie trafia do modelu** w żadnym wariancie. Ma za dużo braków, a adres
  w RCN wypełniany jest częściej w miastach, więc sam brak niósłby informację o typie rynku.

---

## 7. Położenie i kształt działki — 5 cech

### `x_2180`, `y_2180` — współrzędne środka działki

- **Gdzie:** `geometria.py`, `dodaj_geometrie`. Środek z cache ULDK uzupełnia
  `uldk/srodki.py`, `dodaj_srodki_uldk`.
- **Jak:** centroid poligonu działki (`shapely`, `centroid`) w układzie EPSG:2180
  (PUWG 1992, metry). `x` rośnie na wschód, `y` na północ.
- **Po co:** pozwalają modelowi drzewiastemu wyciąć obszary o podobnej cenie bez
  podawania nazw. Są też podstawą wszystkich odległości OSM i sąsiedztwa cenowego.
- **Wartości:**

| | min | p25 | mediana | p75 | max | ρ |
|---|---:|---:|---:|---:|---:|---:|
| `x_2180` | 172 679 | 394 391 | 495 983 | 615 550 | 846 280 | −0,175 |
| `y_2180` | 146 539 | 295 792 | 436 678 | 570 127 | 774 748 | +0,087 |

  Bez braków (do modelu trafiają tylko działki z granicą).
- **Przy wycenie:** z granicy działki wskazanej na mapie.

### `powierzchnia_m2` — powierzchnia działki

- **Gdzie:** `geometria.py`, `ustal_powierzchnie` (opis w 2.2).
- **Jak:** powierzchnia z ewidencji potwierdzona polem z granic (tolerancja 0,80–1,25,
  z rozpoznaniem hektarów). Zakres 100–200 000 m².
- **Po co:** większe działki mają niższą cenę za metr. To jedna z najsilniejszych cech.
- **Wartości:** min 100, p25 956, mediana 1 500, p75 4 458, p99 53 600, max 200 000 m².
  Średnia 5 250 m². Bez braków. **ρ = −0,577.**
- **Przy wycenie:** z granic działki, z możliwością poprawy przez użytkownika.

### `log_powierzchnia` — logarytm powierzchni

- **Gdzie:** `pozostale.py`, `dodaj_pozostale`: `np.log(powierzchnia_m2)`.
- **Po co:** ściska prawoskośny rozkład. Pomaga modelom liniowym. Dla drzew niczego
  nie zmienia, bo podział po logarytmie jest równoważny podziałowi po powierzchni.
- **Wartości:** min 4,61 (= ln 100), p25 6,86, mediana 7,31, p75 8,40, p99 10,89,
  max 12,21 (= ln 200 000). ρ = −0,577, identyczne jak dla powierzchni, bo Spearman
  patrzy tylko na kolejność.
- **Przy wycenie:** liczony z powierzchni.

### `wskaznik_zwartosci` — zwartość kształtu

- **Gdzie:** `pozostale.py`, `dodaj_pozostale`.
- **Jak:** `4π × pole_geom_m2 / obwod_m²`. Pusty, gdy obwód nie jest dodatni.
  Etap sprawdza, że wszystkie wartości mieszczą się w 0–1.
- **Po co:** wąski pas jest trudny do zabudowy i typowy dla gruntów rolnych. Kształt
  zbliżony do kwadratu jest typowy dla działek budowlanych.
- **Jak czytać:** koło = 1, kwadrat = 0,785, prostokąt 1:2 = 0,698, prostokąt 1:10 = 0,260,
  pas 1:50 = 0,060.
- **Wartości:** min 0,002, p1 0,048, p25 0,396, mediana 0,644, p75 0,743, p99 0,810,
  max 0,989. Bez braków. **ρ = +0,417:** im bardziej zwarta działka, tym droższa.
- **Przy wycenie:** z granic działki.

---

## 8. Czas — 2 cechy

### `rok` — rok transakcji

- **Gdzie:** `czyszczenie.py`, `wyczysc_partie`: rok z `dok_data` (data aktu).
- **Po co:** ogólny poziom cen w danym roku.
- **Wartości:** trening obejmuje lata 2015–2024, test 2025–2026. Liczba transakcji
  w zbiorze do modelu:

| 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 19 187 | 35 619 | 44 371 | 51 674 | 58 059 | 67 577 | 98 354 | 74 911 | 73 305 | 84 700 | 92 822 | 32 123 |

  \* do 25.09.2026. Mediana roku 2021. ρ = +0,105.
- **Przy wycenie:** rok daty wyceny.

### `miesiace_od_2015` — ciągła oś czasu

- **Gdzie:** `pozostale.py`, `dodaj_pozostale`: `(rok − 2015) × 12 + miesiąc − 1`.
- **Po co:** dokładniejszy trend cen niż sam rok. Styczeń 2015 = 0, grudzień 2024 = 119.
- **Wartości:** w treningu 0–119 (mediana 75), w teście 120–140. ρ = +0,106.
- **Uwaga:** test leży poza zakresem treningu. Drzewa nie ekstrapolują, więc dla dat
  po 2024 roku przyjmą poziom z końca treningu. Model liniowy przedłuży trend.
  Wycena „na przyszłość” poza datą danych nie ma podstaw.
- **Przy wycenie:** z daty wyceny.

---

## 9. Otoczenie z OpenStreetMap — 27 cech

### 9.1. Jak powstają warstwy

**Źródło:** `backend/db/dane/surowe/osm/poland-260930.osm.pbf` (2,1 GB, Geofabrik,
stan z 30.09.2026).

**Gdzie:** `cechy_osm/warstwy.py`, `przygotuj_warstwy` i `wybierz_warstwy`. Plik jest
czytany strumieniowo przez `pyosmium` z indeksem węzłów na dysku. Każdy obiekt z tagami
dostaje typ (punkt, linia lub obszar), a `wybierz_warstwy` przypisuje go do warstw według
tagów. Geometria jest przeliczana z EPSG:4326 na EPSG:2180 (`pyproj`), a niepoprawne
geometrie są pomijane (12 obszarów). Wynik to 23 pliki parquet z geometrią WKB
i centroidem. Odczyt trwał 5 151 s.

| Warstwa | Warunek w tagach OSM | Typ | Obiekty |
|---|---|---|---:|
| budynki | `building=*` oprócz `no` | obszar | 17 796 971 |
| mieszkalne | `building` = `house`, `residential`, `apartments`, `detached` | obszar | 3 716 078 |
| zabudowa | `landuse=residential` | obszar | 706 539 |
| las | `landuse=forest` lub `natural=wood` | obszar | 923 933 |
| woda | `natural=water` | obszar | 316 159 |
| granica | `boundary=administrative`, `admin_level=2`, `ISO3166-1=PL`, jako obrys | obszar | 1 |
| drogi | każda `highway` oprócz `footway`, `path`, `steps`, `track`, `cycleway`, `bridleway`, `proposed`, `construction`, `platform` | linia | 3 183 339 |
| utwardzone | drogi z `surface` = `asphalt`, `concrete`, `paving_stones`, `sett`, `paved`, `concrete:plates`, `concrete:lanes` | linia | 1 069 003 |
| główne | `highway` = `primary`, `trunk`, `primary_link`, `trunk_link` | linia | 84 465 |
| lokalne | `highway=residential` | linia | 608 418 |
| autostrady | `highway=motorway` | linia | 21 510 |
| rzeki | `waterway=river` | linia | 20 190 |
| węzły | `highway=motorway_junction` | punkt | 1 821 |
| przystanki | `highway=bus_stop` | punkt | 136 928 |
| miejscowości | `place` = `city`, `town`, `village` | punkt | 48 505 |
| miasta | `place` = `city`, `town` | punkt | 1 042 |
| miasta 10k | miasta z `population` > 10 000 | punkt | 392 |
| miasta 50k | miasta z `population` > 50 000 | punkt | 86 |
| wroclaw | `place=city`, `name=Wrocław` | punkt | 1 |
| szkoły | `amenity=school` | dowolny | 18 692 |
| przedszkola | `amenity=kindergarten` | dowolny | 10 663 |
| sklepy | `shop` = `supermarket`, `convenience` | dowolny | 50 773 |
| poi | dowolne `amenity` lub `shop` | dowolny | 1 666 971 |

Szkoły, przedszkola, sklepy i POI są zbierane z punktów i obszarów naraz. Wiele szkół
jest w OSM narysowanych jako obrys budynku, więc same punkty dałyby duże niedoszacowanie.

### 9.2. Jak liczone są cechy

**Gdzie:** `cechy_osm/polska.py`, `policz_osm`. Liczone tylko dla transakcji do modelu,
z ich środków. Trwało 944 s. Żadna z 27 cech nie ma braków. Używane są trzy metody:

1. **Odległość do najbliższej geometrii** (`odleglosci_do_geometrii`): drzewo
   `shapely.STRtree` na pełnych geometriach warstwy i `query_nearest`, partiami po
   10 000 punktów. Mierzona jest odległość do linii lub krawędzi obszaru, a nie do jego
   środka. Punkt wewnątrz obszaru ma 0.
2. **Liczba obiektów w promieniu** (`scipy.spatial.cKDTree`,
   `query_ball_point(..., return_length=True)`): liczone są centroidy obiektów.
3. **Udział powierzchni w kole 500 m** (`pokrycie`): koło `buffer(500, quad_segs=16)`,
   przecięcie z obszarami warstwy, `union_all`, żeby nakładające się obszary liczyć raz,
   pole podzielone przez pole koła i obcięte do 0–1. Partie po 1 000 punktów.

OSM opisuje stan z 2026 roku, a transakcje sięgają 2015 roku. Skutki opisuje rozdział 13.

### 9.3. Zabudowa — 7 cech

#### `odl_najblizszy_budynek_m` — odległość do najbliższego budynku

- **Jak:** metoda 1, warstwa „budynki”.
- **Po co:** bliskość zabudowy oznacza zwykle dostęp do mediów i drogi oraz grunt bliższy
  budowlanemu.
- **Wartości:** min 0, p25 15,2, mediana 35,0, p75 117,3, p99 894,6, max 4 880 m.
  Zero (środek w obrysie budynku): 8,1%. **ρ = −0,601**, najsilniej ze wszystkich cech OSM.
- **Uwaga:** zero przy działce sprzedanej jako niezabudowana oznacza, że budynek powstał
  po sprzedaży. W treningu dotyczy to 9,48% transakcji, w teście 1,42%. Szczegóły w 13.1.

#### `liczba_budynkow_250m`, `liczba_budynkow_500m`, `liczba_budynkow_1000m` — gęstość zabudowy

- **Jak:** metoda 2 na centroidach warstwy „budynki”, promienie 250, 500 i 1 000 m.
- **Po co:** odróżniają osiedle, wieś ulicówkę i pole. Trzy promienie opisują skalę:
  najbliższe sąsiedztwo, okolicę i całą miejscowość.

| Cecha | min | p25 | mediana | p75 | p99 | max | zera | ρ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `liczba_budynkow_250m` | 0 | 8 | 31 | 66 | 263 | 821 | 13,2% | +0,589 |
| `liczba_budynkow_500m` | 0 | 41 | 107 | 220 | 843 | 1 835 | 4,8% | +0,580 |
| `liczba_budynkow_1000m` | 0 | 163 | 348 | 701 | 2 612 | 5 407 | 0,7% | +0,569 |

#### `odl_budynek_mieszkalny_m` — odległość do najbliższego budynku mieszkalnego

- **Jak:** metoda 1, warstwa „mieszkalne”.
- **Po co:** bliżej domów to bardziej mieszkaniowy charakter okolicy niż przy zwykłym
  budynku gospodarczym.
- **Wartości:** min 0, p25 36,8, mediana 102,0, p75 299,8, p99 1 614, max 6 926 m.
  Zero: 3,7%. ρ = −0,517.
- **Uwaga:** wiele domów ma w OSM tylko `building=yes`, więc warstwa jest niepełna,
  a odległości bywają zawyżone.

#### `udzial_zabudowy_500m` — udział terenów mieszkaniowych w promieniu 500 m

- **Jak:** metoda 3, warstwa „zabudowa” (`landuse=residential`).
- **Po co:** jaka część okolicy jest zagospodarowana pod mieszkania.
- **Wartości:** min 0, p25 0,001, mediana 0,104, p75 0,254, p99 0,725, max 1.
  Zero: 24,3%. ρ = +0,546.

#### `czy_w_terenie_zabudowanym` — czy środek leży w terenie mieszkaniowym

- **Jak:** metoda 1 dla warstwy „zabudowa”. 1, gdy odległość wynosi 0, w przeciwnym
  razie 0.
- **Po co:** prosta flaga „w obrębie osiedla lub wsi” kontra „poza nimi”.
- **Wartości:** 1 dla 25,39% transakcji (186 010). Mediana ceny: **89,4 zł/m²** przy 1
  i **24,7 zł/m²** przy 0. ρ = +0,393.

### 9.4. Drogi i transport — 7 cech

| Cecha | Warstwa | min | p25 | mediana | p75 | p99 | max | ρ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `odl_droga_dowolna_m` | drogi | 0 | 22,5 | 37,3 | 113,5 | 841,8 | 5 193 | −0,590 |
| `odl_droga_utwardzona_m` | utwardzone | 0 | 55,5 | 140,6 | 334,8 | 1 640 | 6 044 | −0,392 |
| `odl_droga_lokalna_m` | lokalne | 0 | 32,5 | 105,2 | 380,3 | 2 042 | 5 943 | −0,555 |
| `odl_droga_glowna_m` | główne | 0,4 | 1 598 | 4 153 | 8 696 | 33 089 | 48 095 | −0,224 |
| `odl_autostrada_m` | autostrady | 0,6 | 3 809 | 9 597 | 19 606 | 51 974 | 87 475 | −0,306 |
| `odl_wezel_autostrady_m` | węzły | 30,4 | 4 357 | 9 420 | 17 939 | 46 689 | 87 621 | −0,348 |
| `odl_przystanek_m` | przystanki | 1,6 | 312,3 | 612,5 | 1 319 | 5 723 | 13 866 | −0,434 |

Wszystkie powstają metodą 1. Wartości w metrach.

- **`odl_droga_dowolna_m`** — dostęp do jakiejkolwiek drogi kołowej. Wykluczenie
  `track` jest kluczowe: drogi polne są niemal wszędzie i zatarłyby różnicę między
  działką przy drodze a działką w polu.
- **`odl_droga_utwardzona_m`** — dojazd utwardzony. Wymaga jawnego tagu `surface`,
  więc droga asfaltowa bez tego tagu nie trafia do warstwy. Cecha mierzy więc też
  kompletność opisu dróg w OSM. Stąd słabszy związek z ceną niż przy dowolnej drodze.
- **`odl_droga_lokalna_m`** — ulice osiedlowe (`residential`). Niska wartość to działka
  w strukturze miejscowości.
- **`odl_droga_glowna_m`** — drogi krajowe i wojewódzkie wyższych klas. Bliskość
  oznacza dojazd, ale też hałas.
- **`odl_autostrada_m`** i **`odl_wezel_autostrady_m`** — sama autostrada to hałas i bariera,
  a węzeł to faktyczny dostęp. Zależność od ceny nie musi być monotoniczna: blisko jest
  głośno, kilka kilometrów od węzła jest dobry dojazd, a kilkadziesiąt kilometrów to
  peryferia. Model drzewiasty może to uchwycić, liniowy nie. Węzłów jest 1 821, więc
  warstwa obejmuje prawdopodobnie także węzły dróg ekspresowych. Warto to sprawdzić
  przed opisem w pracy.
- **`odl_przystanek_m`** — transport publiczny. Uwzględnia tylko `highway=bus_stop`,
  bez przystanków tramwajowych i stacji kolejowych.

### 9.5. Miejscowości i miasta — 5 cech

| Cecha | Warstwa | min | p25 | mediana | p75 | p99 | max | ρ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `odl_najblizsza_miejscowosc_m` | miejscowości | 0,6 | 558,9 | 918,0 | 1 391 | 4 677 | 8 834 | +0,111 |
| `odl_miasto_pow_10k_m` | miasta 10k | 24,5 | 5 294 | 9 520 | 14 700 | 30 025 | 64 461 | −0,375 |
| `odl_miasto_pow_50k_m` | miasta 50k | 27,9 | 11 834 | 22 209 | 35 569 | 65 634 | 81 599 | −0,378 |
| `odl_wroclaw_m` | wroclaw | 1 415 | 158 963 | 245 129 | 348 082 | 499 905 | 551 853 | −0,113 |
| `ludnosc_najblizszego_miasta` | miasta | 306 | 4 478 | 13 291 | 32 962 | 800 653 | 1 863 845 | +0,378 |

- **`odl_najblizsza_miejscowosc_m`** — odległość do punktu `place` najbliższego miasta
  lub wsi. Punkt `place` leży w centrum miejscowości. Dodatnie ρ wynika z tego, że
  działki w dużych miastach leżą kilometry od punktu centrum, a są najdroższe. Cecha
  opisuje więc raczej położenie względem centrum niż „odludzie”.
- **`odl_miasto_pow_10k_m`, `odl_miasto_pow_50k_m`** — dojazd do rynku pracy i usług.
  Liczba mieszkańców pochodzi z tagu `population`. Miasto bez tego tagu nie trafia do
  warstwy (392 miasta powyżej 10 tys., 86 powyżej 50 tys.).
- **`ludnosc_najblizszego_miasta`** — liczba mieszkańców miasta, którego punkt `place`
  jest najbliżej (`cKDTree.query` na centroidach warstwy „miasta”). Rozróżnia sąsiedztwo
  dużego miasta i małego miasteczka. Maksimum 1 863 845 to Warszawa.
- **`odl_wroclaw_m`** — **pozostałość po etapie, gdy dane obejmowały tylko Dolny Śląsk.**
  Dla całej Polski nie ma uzasadnienia (dlaczego Wrocław, a nie Kraków czy Poznań)
  i słabo wiąże się z ceną (ρ = −0,113). Proponuję usunąć ją z wejść przed treningiem
  albo zastąpić odległością do najbliższego miasta wojewódzkiego.

### 9.6. Usługi — 4 cechy

| Cecha | Warstwa | min | p25 | mediana | p75 | p99 | max | zera | ρ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `odl_szkola_m` | szkoły | 0 | 809,9 | 1 521 | 2 774 | 7 496 | 15 225 | 0,0% | −0,364 |
| `odl_sklep_spozywczy_m` | sklepy | 0 | 511,0 | 1 022 | 1 983 | 5 591 | 12 304 | 0,1% | −0,456 |
| `odl_przedszkole_m` | przedszkola | 0 | 1 251 | 2 818 | 5 486 | 14 638 | 27 246 | 0,0% | −0,457 |
| `liczba_poi_1km` | poi | 0 | 1 | 6 | 27 | 1 290 | 7 617 | 19,9% | +0,532 |

- **Odległości** (metoda 1, w metrach) — codzienna infrastruktura, ważna przy działkach
  pod dom.
- **`liczba_poi_1km`** (metoda 2, promień 1 000 m) — ogólna „miejskość” okolicy: wszystkie
  obiekty z tagiem `amenity` lub `shop`. Średnia 66,7 przy medianie 6, czyli rozkład
  bardzo skośny. Ten sam obiekt bywa w OSM zarówno punktem, jak i obszarem, więc może
  być policzony dwa razy.

### 9.7. Środowisko i granica — 4 cechy

#### `udzial_lasu_500m` — udział lasu w promieniu 500 m

- **Jak:** metoda 3, warstwa „las”.
- **Po co:** las w pobliżu może podnosić cenę działek rekreacyjnych, a obniżać rolnych.
- **Wartości:** min 0, p25 0,008, mediana 0,070, p75 0,220, p99 0,747, max 1.
  Zero: 16,1%. **ρ ≈ 0,000:** brak zależności monotonicznej. To przykład cechy, którą
  może wykorzystać tylko model nieliniowy, razem z rodzajem gruntu.

#### `odl_woda_m` — odległość do zbiornika wodnego

- **Jak:** metoda 1, warstwa „woda” (`natural=water`: jeziora, stawy, także szerokie
  rzeki narysowane jako obszar). Bez rzek liniowych.
- **Wartości:** min 0, p25 230,3, mediana 436,4, p75 782,5, p99 2 777, max 8 492 m.
  ρ = −0,197.

#### `czy_woda_w_200m` — woda w promieniu 200 m

- **Jak:** 1, gdy zbiornik wodny albo rzeka (`waterway=river`) jest bliżej niż 200 m.
  Brak wiedzy o wodzie i rzekach daje brak, a nie 0 (kod przewiduje to na wypadek pustej
  warstwy).
- **Po co:** atrakcyjność rekreacyjna, ale też ryzyko podtopień.
- **Wartości:** 1 dla 23,02% transakcji (168 636). Mediana ceny 45,6 zł/m² przy 1
  i 39,0 zł/m² przy 0. ρ = +0,054.

#### `odl_granica_panstwa_m` — odległość do granicy Polski

- **Jak:** metoda 1 do obrysu poligonu Polski (`admin_level=2`). Obrys obejmuje też
  granicę morską, więc dla Pomorza „granica” to brzeg morski.
- **Po co:** w planach miała wychwycić rynek przygraniczny.
- **Wartości:** min 2,4, p25 40 571, mediana 74 941, p75 141 852, max 246 895 m.
  ρ = +0,018, czyli brak zależności monotonicznej.

---

## 10. Przeznaczenie z RCN — 27 cech

**Gdzie:** `pozostale.py`, `dodaj_pozostale`. Słownik 24 kategorii jest zapisany w kodzie
jako stała `PRZEZNACZENIA`, wspólna dla całego kraju oraz treningu i testu.

**Jak:** pole RCN `dzi_przezn_wmpzp` zawiera zero, jedną lub kilka kategorii rozdzielonych
`;`. Tekst jest dzielony po `;` i przycinany, a następnie dla każdej z 24 kategorii
powstaje flaga `przezn_<kategoria>` = 1, gdy kategoria występuje we wpisie. Dodatkowo:

- `przezn_brak_danych` = 1, gdy wpis jest pusty,
- `przezn_nieznana_kategoria` = 1, gdy wpis zawiera kategorię spoza słownika,
- `ma_wpis_przeznaczenia` = 1, gdy wpis zawiera cokolwiek, także „brak planu”.

**Ważne rozróżnienia:**

- `przezn_brakMPZPLubWZ` to **informacja**, że działka nie ma planu ani decyzji WZ.
  `przezn_brak_danych` to **brak informacji**. Te dwie flagi znaczą co innego.
- `ma_wpis_przeznaczenia` mówi tylko, że RCN coś zawiera. Nie potwierdza, że obowiązuje
  plan miejscowy. Zastąpiła starą, błędną cechę `ma_mpzp`.
- Działka może mieć kilka kategorii naraz. Suma udziałów 24 flag to około 69%, a wpis
  ma 57,2% transakcji, więc działka z wpisem ma średnio około 1,2 kategorii.

**Po co:** przeznaczenie w planie decyduje o tym, czy można budować. Działka budowlana
i rolna w tym samym miejscu różnią się wielokrotnie.

**Przy wycenie:** jedna odpowiedź w formularzu, z podpowiedzią najczęstszej kategorii
w obrębie, zamieniana na te same flagi tym samym słownikiem.

| Cecha `przezn_…` | Znaczenie | Transakcje z 1 | Udział | Mediana przy 1 | Mediana przy 0 | ρ |
|---|---|---:|---:|---:|---:|---:|
| `budownictwoMieszkanioweJednorodzinne` | zabudowa jednorodzinna | 173 530 | 23,68% | **80,8** | 27,0 | +0,326 |
| `brakMPZPLubWZ` | brak planu i WZ | 118 309 | 16,15% | 15,1 | 44,9 | −0,149 |
| `terenRolniczy` | teren rolniczy | 64 875 | 8,85% | **5,3** | 46,2 | −0,267 |
| `innyNiewymieniony` | inne | 34 224 | 4,67% | 41,7 | 40,0 | +0,008 |
| `terenZabudowyUslugowej` | zabudowa usługowa | 30 203 | 4,12% | 97,7 | 38,8 | +0,139 |
| `terenDrogPublicznych` | droga publiczna | 21 252 | 2,90% | 60,0 | 40,0 | +0,052 |
| `terenZabudowyZagrodowejGospodarstwRolnych` | zabudowa zagrodowa | 13 603 | 1,86% | 27,4 | 40,1 | −0,025 |
| `terenDrogWewnetrznych` | droga wewnętrzna | 10 171 | 1,39% | 45,6 | 40,0 | +0,015 |
| `las` | las | 7 544 | 1,03% | 6,2 | 40,5 | −0,078 |
| `budownictwoMieszkanioweWielorodzinne` | zabudowa wielorodzinna | 6 612 | 0,90% | **298,3** | 40,0 | +0,104 |
| `terenObiektowProdukcyjnychSkladowIMagazynow` | produkcja, składy, magazyny | 6 126 | 0,84% | 81,0 | 40,0 | +0,047 |
| `decyzjaWarunkiZabudowy` | decyzja o warunkach zabudowy | 4 964 | 0,68% | 75,0 | 40,0 | +0,034 |
| `terenSportuIRekreacji` | sport i rekreacja | 3 641 | 0,50% | 55,0 | 40,0 | +0,021 |
| `terenZieleniUrzadzonej` | zieleń urządzona | 3 319 | 0,45% | 65,6 | 40,0 | +0,024 |
| `terenZieleniObjetyFormaOchronyPrzyrody` | zieleń chroniona | 1 823 | 0,25% | 18,0 | 40,0 | −0,014 |
| `terenWodPowierzchniowychSrodladowych` | wody śródlądowe | 1 504 | 0,21% | 16,0 | 40,0 | −0,015 |
| `obszarITerenGorniczy` | teren górniczy | 1 143 | 0,16% | 32,3 | 40,0 | −0,002 |
| `terenInfrastrukturyTechnicznej` | infrastruktura techniczna | 824 | 0,11% | 51,2 | 40,0 | +0,008 |
| `terenOgrodowDzialkowych` | ogrody działkowe | 710 | 0,10% | 21,5 | 40,0 | −0,009 |
| `terenObslugiProdukcjiWGospodarstwachRolnych` | obsługa produkcji rolnej | 427 | 0,06% | 8,8 | 40,0 | −0,014 |
| `terenRozmieszczeniaDuzcychObiektowHandlowych` | duże obiekty handlowe | 395 | 0,05% | 73,8 | 40,0 | +0,011 |
| `cmentarz` | cmentarz | 98 | 0,01% | 29,3 | 40,0 | −0,003 |
| `terenKomunikacjiWodnejSzlakWodny` | szlak wodny | 64 | 0,01% | 60,2 | 40,0 | +0,004 |
| `terenWodPowierzchniowychMorskich` | wody morskie | 4 | 0,00% | 63,2 | 40,0 | +0,001 |

Mediany w zł/m², liczone na treningu.

| Cecha | Transakcje z 1 | Udział | Mediana przy 1 | Mediana przy 0 | ρ |
|---|---:|---:|---:|---:|---:|
| `przezn_brak_danych` | 313 350 | 42,77% | 35,2 | 45,0 | −0,058 |
| `ma_wpis_przeznaczenia` | 419 352 | 57,23% | 45,0 | 35,2 | +0,058 |
| `przezn_nieznana_kategoria` | 0 | 0% | — | — | — |

`przezn_brak_danych` i `ma_wpis_przeznaczenia` są dokładnym przeciwieństwem, więc jedna
z nich jest nadmiarowa. `przezn_nieznana_kategoria` jest stała (słownik obejmuje wszystkie
kategorie w danych) i audyt usuwa ją z wejść. Zostaje w kodzie na wypadek nowych danych.
Kilka kategorii ma poniżej 100 transakcji (cmentarz, szlak wodny, wody morskie), więc
ich flagi niewiele wniosą.

---

## 11. Sąsiedztwo cenowe — 8 cech

**Gdzie:** `sasiedztwo_cenowe/polska.py`, `dodaj_sasiedztwo`. Przeliczenie do walidacji
(odcięcie 2024-01-01): `walidacja_modelu.py` i `model/przygotowanie.py`,
`przygotuj_walidacje`.

**Po co:** cena za m² w okolicy to najlepsza pojedyncza wskazówka ceny działki. Tak samo
wycenia rzeczoznawca w podejściu porównawczym.

### 11.1. Zasady, które chronią przed wyciekiem ceny

Te cechy zawierają ceny, czyli to, co model przewiduje. Liczone nieostrożnie dałyby
sztucznie świetny wynik. Dlatego dla każdej transakcji *i*:

1. **Tylko wcześniejszy dzień:** referencją jest transakcja z datą ściśle wcześniejszą
   niż data *i* (dni bez godzin, `dok_data.dt.normalize()`). Transakcje z tego samego dnia
   się nie liczą.
2. **Tylko trening:** referencjami są wyłącznie transakcje treningowe (przed 2025-01-01).
   Ceny testowe nigdy nie trafiają do cech innych transakcji, także testowych.
3. **Bez tej samej działki:** wcześniejsze sprzedaże działki o tym samym identyfikatorze
   są pomijane.
4. **Bez granic administracyjnych w oknach przestrzennych:** koła 2 i 5 km mogą
   przekraczać granice gmin, powiatów i województw. Gmina i obręb ograniczają tylko
   swoje mediany i trend.
5. **Okna czasowe** są kalendarzowe (`pd.DateOffset(months=24)`), z dolną granicą
   włącznie. Dzień wycenianej transakcji jest wyłączony.
6. **Brak sąsiadów** daje pustą medianę i odległość, a licznik transakcji wynosi 0.
   Braki nie są uzupełniane medianą z całego zbioru ani przyszłymi cenami.

**Skutek dla testu:** baza referencji jest „zamrożona” na 31.12.2024. Dla późnych
transakcji testowych okno 24 miesięcy zawiera mniej sprzedaży, stąd więcej braków
w teście, zwłaszcza w trendzie.

**Zmiana daty podziału wymaga ponownego policzenia wszystkich ośmiu cech.** Tabela
nie nadaje się do losowej walidacji krzyżowej.

### 11.2. Jak liczone

Mediany w gminie i obrębie: grupowanie po `teryt_gmina` i `teryt_obreb`, referencje
w grupie posortowane po dacie, `np.searchsorted` wycina wcześniejsze.

Cechy przestrzenne: drzewo `cKDTree` na środkach transakcji treningowych.
Dla każdej transakcji `query_ball_point(r=5000)`, filtr daty i działki, odległości
liczone dokładnie (`np.linalg.norm`). Dla najbliższej transakcji spoza 5 km drzewo jest
pytane o coraz więcej sąsiadów (32, 64, …), aż znajdzie dopuszczalną referencję.

### 11.3. Cechy

| Cecha | Definicja |
|---|---|
| `mediana_cena_m2_2km_ten_sam_uzytek` | mediana ceny za m² w promieniu 2 km z ostatnich 24 miesięcy, tylko transakcje z tym samym niepustym `dzi_sposob_uzyt` |
| `mediana_cena_m2_2km_24m` | mediana w promieniu 2 km z ostatnich 24 miesięcy, bez względu na użytek |
| `mediana_cena_m2_5km_24m` | mediana w promieniu 5 km z ostatnich 24 miesięcy |
| `mediana_cena_m2_obreb` | mediana wszystkich dopuszczalnych wcześniejszych sprzedaży w obrębie, bez limitu czasu |
| `mediana_cena_m2_gmina` | mediana wszystkich dopuszczalnych wcześniejszych sprzedaży w gminie, bez limitu czasu |
| `liczba_transakcji_2km_24m` | ile sprzedaży złożyło się na medianę 2 km, czyli miara pewności |
| `trend_cen_gmina_12m` | mediana z ostatnich 12 miesięcy w gminie / mediana z 12 miesięcy wcześniejszych − 1. Wymaga co najmniej jednej sprzedaży w każdym oknie |
| `odl_najblizsza_transakcja_m` | odległość do najbliższej dopuszczalnej wcześniejszej sprzedaży, bez limitu 24 miesięcy i 5 km |

### 11.4. Wartości

| Cecha | Braki T | Braki S | min | p25 | mediana | p75 | p99 | max | ρ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `mediana_cena_m2_2km_ten_sam_uzytek` | 54 324 (8,9%) | 13 755 (11,0%) | 0,0005 | 13,3 | 45,0 | 96,3 | 698,4 | 1 397 223 | **+0,742** |
| `mediana_cena_m2_2km_24m` | 21 871 (3,6%) | 5 629 (4,5%) | 0,0013 | 14,1 | 44,6 | 95,0 | 624,5 | 129 021 | **+0,730** |
| `mediana_cena_m2_obreb` | 38 791 (6,4%) | 3 973 (3,2%) | 0,0005 | 10,0 | 38,7 | 79,6 | 593,3 | 6,4·10¹⁰ | **+0,730** |
| `mediana_cena_m2_5km_24m` | 3 195 (0,5%) | 586 (0,5%) | 0,0026 | 14,2 | 41,9 | 87,1 | 477,8 | 45 022 | +0,701 |
| `mediana_cena_m2_gmina` | 2 786 (0,5%) | 539 (0,4%) | 0,0036 | 10,0 | 36,1 | 75,0 | 381,4 | 26 410 | +0,693 |
| `liczba_transakcji_2km_24m` | 0 | 0 | 0 | 6 | 16 | 31 | 166 | 631 | +0,523 |
| `odl_najblizsza_transakcja_m` | 2 | 0 | 0 | 60,9 | 172,8 | 413,9 | 3 486 | 252 940 | −0,429 |
| `trend_cen_gmina_12m` | 74 629 (12,3%) | 36 659 (29,3%) | −1,00 | −0,083 | +0,099 | +0,331 | 4,87 | 8 052 | −0,006 |

Ceny w zł/m², odległości w metrach, trend jako ułamek (0,099 = +9,9%).

**Jak czytać:**

- **Mediany cen to najsilniejsze cechy w całym zbiorze** (ρ 0,69–0,74). Najlepsza jest
  mediana w 2 km dla tego samego użytku, bo porównuje działkę rolną z rolnymi,
  a budowlaną z budowlanymi.
- Mediany przenoszą skrajne ceny z rozdziału 3. Maksimum mediany w obrębie
  (6,4·10¹⁰ zł/m²) to jedna absurdalna cena w małym obrębie. Średnia tej cechy
  (140 323 zł/m²) jest przez to bezużyteczna. Drzewom to nie przeszkadza, ale modele
  liniowe trzeba karmić logarytmem albo obciętymi wartościami.
- Mediany 2 km i 5 km są pomijane, gdy w oknie nie ma sprzedaży. Wtedy obręb i gmina
  działają jak zapas, bo nie mają limitu czasu.
- `liczba_transakcji_2km_24m` mówi, jak bardzo ufać medianie 2 km. 3,8% transakcji
  nie ma w tym oknie żadnej referencji.
- `trend_cen_gmina_12m` jest niestabilny przy małych próbach. Maksimum 8 052 oznacza
  wzrost mediany 8 053 razy, a −1 to spadek do zera. Związek z ceną jest zerowy.
  W teście ma 29% braków. To kandydat do usunięcia albo do liczenia tylko przy minimalnej
  liczbie transakcji w obu oknach.
- `odl_najblizsza_transakcja_m` = 0 (0,1%) to inna działka o tym samym środku, np. po
  podziale lub zmianie numeracji. 2 braki w treningu to transakcje z pierwszego dnia
  danych.

**Przy wycenie:** z bazy wcześniejszych transakcji i daty wyceny. Mediana
„ten sam użytek” wymaga rodzaju gruntu z formularza.

---

## 12. Co trafia do modelu: warianty „mapa” i „formularz”

Audyt (`audyt_danych.py`, `dostepnosc_cech`) przypisuje każdą cechę do źródła,
z którego da się ją uzyskać przy wycenie nowej działki:

| Źródło przy wycenie | Cechy |
|---|---|
| geometria działki | `x_2180`, `y_2180`, `powierzchnia_m2`, `log_powierzchnia`, `wskaznik_zwartosci` |
| identyfikator działki | `teryt_woj`, `teryt_powiat`, `teryt_gmina` |
| data wyceny | `rok`, `miesiace_od_2015` |
| warstwy OSM | 27 cech z rozdziału 9 |
| baza referencji RCN | 7 cech sąsiedztwa (bez „ten sam użytek”) |
| formularz | `tran_sprzedajacy`, `nier_prawo`, `dzi_sposob_uzyt` |
| formularz: przeznaczenie | 26 flag `przezn_*` i `ma_wpis_przeznaczenia` |
| formularz + baza referencji | `mediana_cena_m2_2km_ten_sam_uzytek` |
| wykluczona | `miejscowosc` (historyczny adres) |

- **Wariant „mapa” — 44 cechy:** geometria, TERYT, czas, 27 cech OSM i 7 cech sąsiedztwa.
  Wystarczy wskazać działkę.
- **Wariant „formularz” — 74 cechy:** „mapa” oraz sprzedający, prawo, rodzaj gruntu,
  przeznaczenie i mediana dla tego samego użytku. **Ten wariant odpowiada panelowi
  zaprojektowanemu w Figmie.**
- Z obu wariantów usunięte są `miejscowosc` i stała `przezn_nieznana_kategoria`.

**Przetwarzanie przed modelem** (`model/przygotowanie.py`, `zbuduj_przetwarzanie`):
liczby — imputacja medianą z flagą braku (`SimpleImputer(strategy="median",
add_indicator=True)`) i standaryzacja. Kategorie — stała `__BRAK__` i one-hot
z ignorowaniem nieznanych kategorii. Wszystko dopasowane **tylko na treningu**
i zapisane razem z modelem w jednym `Pipeline`.

---

## 13. Ograniczenia i ryzyka

### 13.1. Aktualne OSM przy historycznych sprzedażach

OSM i granice EGiB opisują stan z 2026 roku, a transakcje sięgają 2015 roku.
Najmocniej widać to przy budynkach. Środek działki sprzedanej jako **niezabudowana**
leży dziś w obrysie budynku w **9,48% transakcji treningowych**, a tylko w **1,42%
testowych**. Starsze działki zdążyły zostać zabudowane po sprzedaży.

To częściowy wyciek informacji z przyszłości: model może się nauczyć, że „budynek na
działce” oznacza wysoką cenę, choć w chwili sprzedaży budynku nie było. Dotyczy to
głównie `odl_najblizszy_budynek_m`, `odl_budynek_mieszkalny_m`, liczby budynków
i udziału zabudowy, a słabiej dróg, przystanków i sklepów.

Co z tym zrobić w pracy:

- opisać to wprost jako ograniczenie,
- sprawdzić wynik modelu bez cech zabudowy albo z flagą „środek w obrysie budynku”,
- wynik na teście (2025–2026) jest tu bardziej wiarygodny niż na treningu, bo test
  leży blisko daty ekstraktu OSM.

### 13.2. Ceny skrajne i udziały

Ceny przeliczone z bardzo małych udziałów dają wartości rzędu miliardów zł/m²
i przenoszą się do median sąsiedztwa. Zostały w danych celowo, bez automatycznego
odcinania. W pracy warto porównać wyniki na wszystkich danych i na samych pełnych
udziałach, na tym samym teście.

### 13.3. Te same działki w treningu i teście

8 270 identyfikatorów działek występuje w obu zbiorach (sprzedane ponownie). Podział
czasowy jest poprawny, ale warto podać też wynik na działkach niewidzianych w treningu.

### 13.4. Nowe kategorie w teście

329 transakcji testowych pochodzi z powiatów, a 539 z gmin nieobecnych w treningu.
One-hot przypisze im same zera, więc model oprze się na współrzędnych i sąsiedztwie.

### 13.5. Jakość tagowania OSM

Cechy OSM zależą od tego, jak dokładnie opisano okolicę: brak tagu `surface`, `population`
czy typu budynku zmienia wartość cechy, choć teren jest taki sam. Wiejskie obszary bywają
opisane słabiej niż miasta.

### 13.6. Cechy do rozważenia przed treningiem

| Cecha | Problem | Propozycja |
|---|---|---|
| `odl_wroclaw_m` | pozostałość po Dolnym Śląsku, brak uzasadnienia dla Polski | usunąć albo zastąpić odległością do miasta wojewódzkiego |
| `trend_cen_gmina_12m` | niestabilny, ρ ≈ 0, 29% braków w teście | usunąć albo liczyć przy minimalnej liczbie transakcji |
| `przezn_brak_danych` | dokładne przeciwieństwo `ma_wpis_przeznaczenia` | zostawić jedną z dwóch |
| `log_powierzchnia` | dla drzew nadmiarowa wobec `powierzchnia_m2` | zostawić tylko dla modeli liniowych |
| `odl_granica_panstwa_m` | ρ ≈ 0, obrys obejmuje brzeg morski | sprawdzić ważność w modelu, ewentualnie usunąć |
| flagi przeznaczenia < 100 transakcji | za mało przykładów | połączyć w grupy albo zostawić bez oczekiwań |

---

## 14. Ranking siły związku z ceną

Korelacja rang Spearmana z `cena_m2` na treningu (607 757 transakcji), od najsilniejszej.
To wskazówka, które cechy niosą najwięcej informacji pojedynczo, a nie ważność w modelu.

| # | Cecha | ρ | | # | Cecha | ρ |
|---:|---|---:|---|---:|---|---:|
| 1 | `mediana_cena_m2_2km_ten_sam_uzytek` | +0,742 | | 26 | `odl_szkola_m` | −0,364 |
| 2 | `mediana_cena_m2_2km_24m` | +0,730 | | 27 | `odl_wezel_autostrady_m` | −0,348 |
| 3 | `mediana_cena_m2_obreb` | +0,730 | | 28 | `przezn_budownictwoMieszkanioweJednorodzinne` | +0,326 |
| 4 | `mediana_cena_m2_5km_24m` | +0,701 | | 29 | `odl_autostrada_m` | −0,306 |
| 5 | `mediana_cena_m2_gmina` | +0,693 | | 30 | `przezn_terenRolniczy` | −0,267 |
| 6 | `odl_najblizszy_budynek_m` | −0,601 | | 31 | `odl_droga_glowna_m` | −0,224 |
| 7 | `odl_droga_dowolna_m` | −0,590 | | 32 | `odl_woda_m` | −0,197 |
| 8 | `liczba_budynkow_250m` | +0,589 | | 33 | `x_2180` | −0,175 |
| 9 | `liczba_budynkow_500m` | +0,580 | | 34 | `przezn_brakMPZPLubWZ` | −0,149 |
| 10 | `powierzchnia_m2` | −0,577 | | 35 | `przezn_terenZabudowyUslugowej` | +0,139 |
| 11 | `log_powierzchnia` | −0,577 | | 36 | `odl_wroclaw_m` | −0,113 |
| 12 | `liczba_budynkow_1000m` | +0,569 | | 37 | `odl_najblizsza_miejscowosc_m` | +0,111 |
| 13 | `odl_droga_lokalna_m` | −0,555 | | 38 | `miesiace_od_2015` | +0,106 |
| 14 | `udzial_zabudowy_500m` | +0,546 | | 39 | `rok` | +0,105 |
| 15 | `liczba_poi_1km` | +0,532 | | 40 | `przezn_budownictwoMieszkanioweWielorodzinne` | +0,104 |
| 16 | `liczba_transakcji_2km_24m` | +0,523 | | 41 | `y_2180` | +0,087 |
| 17 | `odl_budynek_mieszkalny_m` | −0,517 | | 42 | `przezn_las` | −0,078 |
| 18 | `odl_przedszkole_m` | −0,457 | | 43 | `ma_wpis_przeznaczenia` | +0,058 |
| 19 | `odl_sklep_spozywczy_m` | −0,456 | | 44 | `przezn_brak_danych` | −0,058 |
| 20 | `odl_przystanek_m` | −0,434 | | 45 | `czy_woda_w_200m` | +0,054 |
| 21 | `odl_najblizsza_transakcja_m` | −0,429 | | 46 | `przezn_terenDrogPublicznych` | +0,052 |
| 22 | `wskaznik_zwartosci` | +0,417 | | 47 | `odl_granica_panstwa_m` | +0,018 |
| 23 | `czy_w_terenie_zabudowanym` | +0,393 | | 48 | `trend_cen_gmina_12m` | −0,006 |
| 24 | `odl_droga_utwardzona_m` | −0,392 | | 49 | `udzial_lasu_500m` | −0,000 |
| 25 | `odl_miasto_pow_50k_m`, `ludnosc_najblizszego_miasta` | ∓0,378 | | — | pozostałe flagi przeznaczenia | \|ρ\| < 0,05 |

Kategorie (`tran_sprzedajacy`, `nier_prawo`, `dzi_sposob_uzyt`, `teryt_*`) nie mają ρ,
bo nie mają porządku. Ich siłę pokazują różnice median w rozdziałach 5 i 6.

---

## Jak odtworzyć liczby

Profil braków i kwantyli: `backend/db/dane/gotowe/audyt_modelu/profile.json`
(z `python -m etl.audyt_danych`). Kwartyle, udziały flag, mediany ceny w grupach
i współczynniki ρ zostały policzone jednorazowo na tym samym pliku, kolumna po kolumnie,
na zbiorze treningowym (ρ i mediany) albo na wszystkich transakcjach (kwartyle, udziały).
Raporty etapów: `podsumowanie.json` i `raport_czyszczenia.csv` w katalogach
`polska_po_egib/`, `polska_cechy_osm/` i `polska_pelne_cechy/`.
