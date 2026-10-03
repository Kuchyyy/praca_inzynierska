> Korekta z 03.10.2026: nieznane udziały są odrzucane, znane udziały częściowe
> służą do proporcjonalnego przeliczenia ceny za m². Braki geometrii zostają. `do_modelu` oddziela rekordy o kompletnych danych podstawowych.
> Czyszczenie korzysta ze starych środków ULDK i nowego cache pełnych granic.
> Domyślnie działa bez sieci; `LIMIT_ULDK` w `config.py` pozwala uzupełniać granice etapami.
> Wcześniejsze liczby i opisy poniżej dokumentują poprzednie warianty.

> Bieżący etap — czyszczenie krajowego RCN
>
> `main.py` wykonuje teraz tylko czyszczenie partiami. Zapisuje GeoParquet
> z geometrią i podstawowymi wielkościami, bez percentyli cen, ULDK i OSM.
> Zasady opisuje README w głównym katalogu. Stary zbiór 76 346 wierszy
> i 64 kolumn pozostaje historycznym wynikiem, nie wynikiem nowego ETL.
> Cechy i modele opisane niżej wymagają jeszcze podłączenia do nowego zbioru.

> Aktualizacja zakresu — 02.10.2026
>
> Dalej rozwijamy RCN, geometrię, sąsiedztwo cenowe oraz OSM: drogi,
> miejscowości, zabudowę, środowisko i usługi. GUS, powodzie, NMT,
> dodatkowe dane planistyczne i BDOT10k są poza aktualnym zakresem.
> Poniżej zachowano wcześniejsze rozważania i pomiary. Podane wagi są
> oceną autora, nie wynikiem eksperymentów ani rankingiem ważności modelu.
> Kod ma obecnie 6 cech sąsiedztwa, 5 odległości OSM i uzupełnianie środków
> z ULDK. Gotowy lokalny zbiór ma 76 346 wierszy i 64 kolumny.
> Dalsze cechy OSM opisane poniżej to propozycje, a nie gotowa implementacja.

# Cechy — skąd pochodzą i jak je policzyć

Dokument opisuje każdą cechę używaną do przewidywania ceny działki: z czego powstaje,
jak ją policzyć i w której wersji programu się pojawia.

## Legenda

**Waga 1–10** — szacunek, jak mocno cecha pomaga przewidzieć cenę za metr kwadratowy.
Cechy o wadze 4 i niższej zostały świadomie odrzucone (lista na końcu dokumentu).

**Wersja 1** — jest już zaimplementowana, liczona wyłącznie z pliku Parquet.
**Wersja 2** — do dołożenia później, wymaga dodatkowych danych lub bibliotek.

**Skąd:**
- `PLIK` — kolumna jest w pliku Parquet, bierzemy ją wprost
- `POCHODNA` — wyliczana z kolumn pliku
- `GEOMETRIA` — z kolumny `geometry` (granice działki zapisane binarnie)
- `OSM` — z pliku OpenStreetMap
- `ZEWNĘTRZNE` — trzeba pobrać z internetu

---

# WERSJA 1 — z pliku Parquet

**Stan po sesji z 22.09 — zweryfikowany na gotowym pliku `dane_z_cechami.parquet`:
76 346 wierszy, 53 kolumny.** Wszystko liczone z jednego pliku, bez pobierania
czegokolwiek. Cały program wykonuje się w około 10 sekund.

**Waga 0** = nie jest cechą modelu (identyfikator, stała po filtrze, surowa wersja
zastąpiona czystszą, albo kolumna czysto diagnostyczna). **TARGET** = to, co model ma
przewidywać, nie wejście. **Waga 1–10** = szacunek siły predykcyjnej.
Suma: **38 kolumn z wagą > 0** (prawdziwe cechy) + **14 z wagą 0** + **1 target** = 53.

| Lp | Kolumna | Co przedstawia | Waga |
|---|---|---|---|
| 1 | `teryt` | Surowy kod powiatu z pliku RCN — bywa niespójny z `dzi_id_dzialki` (150/1 184 944 wierszy, 0,013% — patrz `prywatne/NOTATKI_DO_PRACY.txt` pkt 1), zastąpiony przez `teryt_powiat`/`teryt_gmina` | 0 |
| 2 | `id_transakcji` | Unikalny identyfikator transakcji z RCN (`tran_lokalny_id_iip`) — 76 346 unikalnych wartości, tyle co wierszy | 0 |
| 3 | `tran_rodzaj_trans` | Rodzaj transakcji — po filtrze krok_07 zawsze `"wolnyRynek"`, zero wariancji | 0 |
| 4 | `sprzedajacy` | Kto sprzedał: osoba fizyczna / prawna / Skarb Państwa / JST / inne — 5 kategorii | 5 |
| 5 | `cena_brutto` | Cena całej transakcji w zł — surowy licznik do `cena_m2`, nie cecha wejściowa | 0 |
| 6 | `data_transakcji` | Data zawarcia transakcji — zastąpiona przez `rok` i `miesiace_od_2015` | 0 |
| 7 | `nier_rodzaj` | Rodzaj nieruchomości — po filtrze krok_06 zawsze `"nieruchomoscGruntowaNiezabudowana"`, zero wariancji | 0 |
| 8 | `prawo` | Rodzaj prawa do nieruchomości: własność / użytkowanie wieczyste — 4 kategorie (+ 1,7% braków) | 5 |
| 9 | `dzi_id_dzialki` | Identyfikator działki wg ewidencji gruntów (woj+powiat+gmina+obręb+numer) — 63 518 unikalnych (część działek sprzedano kilka razy); źródło kolumn 14–16 | 0 |
| 10 | `dzi_przezn_wmpzp` | Surowe przeznaczenie z planu miejscowego, tekst rozdzielony `;` (66,5% wypełnienia) — zastąpione przez 24 kolumny `przezn_*` | 0 |
| 11 | `dzi_pow_ewid` | Surowa powierzchnia z ewidencji gruntów — miesza hektary i m² bez rozróżnienia — zastąpiona przez `powierzchnia_m2` | 0 |
| 12 | `sposob_uzytkowania` | Sposób użytkowania gruntu: rolne / leśne / zabudowane-zurbanizowane / komunikacyjne / inne — 5 kategorii, mediany ceny różnią się 34-krotnie między nimi | 8 |
| 13 | `dzi_adres` | Surowy adres tekstowy `MSC:...;UL:...;NR_PORZ:...` (41,0% wypełnienia) — zastąpiony przez `miejscowosc` | 0 |
| 14 | `teryt_woj` | Kod województwa (2 cyfry) wyliczony z `dzi_id_dzialki` — po filtrze krok_03 zawsze `"02"`, zero wariancji | 0 |
| 15 | `teryt_powiat` | Kod powiatu (4 cyfry) wyliczony z `dzi_id_dzialki` — 29 powiatów w zbiorze | 8 |
| 16 | `teryt_gmina` | Kod gminy (6 cyfr) wyliczony z `dzi_id_dzialki` — 160 gmin, mediana 316 transakcji/gminę | 9 |
| 17 | `rok` | Rok transakcji (`dok_data.dt.year`) — 12 lat, 2015–2026 | 8 |
| 18 | `pole_geom_m2` | Pole działki policzone z granic geometrii (`ksztalt.area`) — 89,8% wypełnienia. Wyłącznie do weryfikacji `powierzchnia_m2`, nie osobna cecha (mediana różnicy 0,08%) | 0 |
| 19 | `obwod_m` | Obwód działki z geometrii (`ksztalt.length`) — 89,8% wypełnienia. Wyłącznie do policzenia `wskaznik_zwartosci` | 0 |
| 20 | `x_2180` | Współrzędna X środka działki, układ EPSG:2180 (metry) — 89,8% wypełnienia | 9 |
| 21 | `y_2180` | Współrzędna Y środka działki, układ EPSG:2180 — zawsze razem z `x_2180` (zero rozjazdów, sprawdzone) | 9 |
| 22 | `powierzchnia_m2` | Ostateczna, zweryfikowana powierzchnia działki w m² — `dzi_pow_ewid` poprawnie przeskalowane i potwierdzone geometrią tam, gdzie to możliwe | 9 |
| 23 | `zrodlo_powierzchni` | Flaga jakości: skąd wzięła się `powierzchnia_m2` — `"geometria"` (89,4%) / `"heurystyka"` (10,2%) / `"pole_z_geometrii"` (0,5%). Diagnostyka, nie cecha ekonomiczna | 0 |
| 24 | `cena_m2` | Cena za metr kwadratowy (`cena_brutto / powierzchnia_m2`) — **TARGET**, to model ma przewidywać, nie wejście | TARGET |
| 25 | `log_powierzchnia` | Logarytm naturalny z `powierzchnia_m2` — ściska silnie prawoskośny rozkład powierzchni | 9 |
| 26 | `przezn_budownictwoMieszkanioweJednorodzinne` | MPZP: pod dom jednorodzinny — 27 569 działek | 9 |
| 27 | `przezn_brak_danych` | Flaga: działka nie ma żadnego wpisu przeznaczenia w planie — 25 591 działek | 9 |
| 28 | `przezn_terenRolniczy` | MPZP: teren rolniczy — 8 876 działek | 9 |
| 29 | `przezn_brakMPZPLubWZ` | MPZP: brak planu lub decyzji o warunkach zabudowy — 5 687 działek | 9 |
| 30 | `przezn_terenZabudowyUslugowej` | MPZP: zabudowa usługowa — 3 753 działki | 9 |
| 31 | `przezn_terenDrogWewnetrznych` | MPZP: droga wewnętrzna — 2 921 działek | 9 |
| 32 | `przezn_innyNiewymieniony` | MPZP: inne, niewymienione wprost — 2 688 działek | 9 |
| 33 | `przezn_terenDrogPublicznych` | MPZP: droga publiczna — 2 135 działek | 9 |
| 34 | `przezn_budownictwoMieszkanioweWielorodzinne` | MPZP: pod blok/wielorodzinne — 1 958 działek | 9 |
| 35 | `przezn_terenZabudowyZagrodowejGospodarstwRolnych` | MPZP: zabudowa zagrodowa gospodarstw rolnych — 1 357 działek | 9 |
| 36 | `przezn_terenObiektowProdukcyjnychSkladowIMagazynow` | MPZP: produkcja/składy/magazyny — 901 działek | 9 |
| 37 | `przezn_terenSportuIRekreacji` | MPZP: sport i rekreacja — 545 działek | 9 |
| 38 | `przezn_las` | MPZP: las — 476 działek | 9 |
| 39 | `przezn_terenZieleniUrzadzonej` | MPZP: zieleń urządzona (park, skwer) — 373 działki | 9 |
| 40 | `przezn_obszarITerenGorniczy` | MPZP: teren górniczy — 319 działek | 9 |
| 41 | `przezn_terenInfrastrukturyTechnicznej` | MPZP: infrastruktura techniczna — 264 działki | 9 |
| 42 | `przezn_terenWodPowierzchniowychSrodladowych` | MPZP: wody śródlądowe — 197 działek | 9 |
| 43 | `przezn_decyzjaWarunkiZabudowy` | MPZP: decyzja o warunkach zabudowy zamiast planu — 176 działek | 9 |
| 44 | `przezn_terenZieleniObjetyFormaOchronyPrzyrody` | MPZP: zieleń chroniona przyrodniczo — 111 działek | 9 |
| 45 | `przezn_terenOgrodowDzialkowych` | MPZP: ogrody działkowe — 86 działek | 9 |
| 46 | `przezn_terenObslugiProdukcjiWGospodarstwachRolnych` | MPZP: obsługa produkcji rolnej — 47 działek | 9 |
| 47 | `przezn_terenKomunikacjiWodnejSzlakWodny` | MPZP: szlak wodny — 29 działek | 9 |
| 48 | `przezn_terenRozmieszczeniaDuzcychObiektowHandlowych` | MPZP: duże obiekty handlowe — 24 działki | 9 |
| 49 | `przezn_cmentarz` | MPZP: cmentarz — 7 działek | 9 |
| 50 | `ma_mpzp` | Flaga 0/1: czy działka w ogóle ma zapisane przeznaczenie (i nie jest to `brakMPZPLubWZ`) | 7 |
| 51 | `miesiace_od_2015` | Liczba miesięcy od stycznia 2015 — ciągła oś czasu, `(rok-2015)*12 + miesiąc - 1`, 140 wartości | 8 |
| 52 | `miejscowosc` | Nazwa miejscowości wyciągnięta z `dzi_adres` (wielkie litery) — 41,0% wypełnienia, 1 598 miejscowości. W tej samej gminie różne miejscowości dają nawet ~9-krotną różnicę mediany ceny (zweryfikowane na gminie 022202: IWNO 24,77 zł/m² vs STRYJNO 2,81 zł/m²) | 7 |
| 53 | `wskaznik_zwartosci` | `4·π·pole_geom_m2 / obwod_m²` — jak bardzo kształt działki przypomina koło (1,0 = koło, blisko 0 = wąski pas). Mediana 0,641; 8 010 działek poniżej 0,2 | 6 |

**Skreślone z tej wersji dokumentu, bo usunięte z kodu:** `teryt_obreb`, `nr_dzialki`,
`kwartal` — szczegóły w sekcji „Cechy odrzucone" niżej.

---

# WERSJA 2 — co dołożyć i skąd to wziąć

## Grupa C — sąsiedztwo cenowe (8 cech, wagi 6–10)

**Źródło: ten sam plik Parquet. Nic nie trzeba pobierać.**
**Potrzebne dodatkowo: `scipy`** (struktura `cKDTree` do szybkiego szukania sąsiadów).

To będą **najsilniejsze cechy w całym modelu**. Idea jest prosta: jeśli działki w okolicy
sprzedawały się po 80 zł/m², to ta prawdopodobnie też jest warta około tyle.

| Cecha | Definicja | Waga |
|---|---|---|
| `mediana_cena_m2_2km_ten_sam_uzytek` | Mediana ceny za m² w promieniu 2 km, ten sam sposób użytkowania, ostatnie 24 miesiące | 10 |
| `mediana_cena_m2_2km_24m` | To samo, bez zawężenia do sposobu użytkowania | 10 |
| `mediana_cena_m2_5km_24m` | Szerszy promień — ratuje tam, gdzie w 2 km nic nie było | 9 |
| `mediana_cena_m2_obreb` | Mediana w obrębie ewidencyjnym | 9 |
| `mediana_cena_m2_gmina` | Mediana w gminie | 8 |
| `liczba_transakcji_2km_24m` | Ile transakcji złożyło się na medianę — miara pewności | 7 |
| `trend_cen_gmina_12m` | Zmiana mediany w gminie rok do roku | 6 |
| `odl_najblizsza_transakcja_m` | Odległość do najbliższej innej transakcji | 6 |

### ⚠️ UWAGA — tu najłatwiej zniszczyć całą pracę

Te cechy zawierają informację o cenie, czyli o tym, co próbujemy przewidzieć. Policzone
nieostrożnie dadzą wynik `R² = 0,95`, który w praktyce okaże się bezwartościowy.

**Trzy zasady, których nie wolno złamać:**

1. **Do cechy wchodzą wyłącznie transakcje o dacie wcześniejszej** niż ta, dla której
   liczymy. Nigdy z przyszłości.
2. **Transakcja nie może wchodzić do własnej cechy.**
3. **Podział na zbiór uczący i testowy musi iść po dacie**, nie losowo.

Szkic poprawnego rozwiązania:

```python
from scipy.spatial import cKDTree

df = df.sort_values("data_transakcji")
drzewo = cKDTree(df[["x_2180", "y_2180"]].values)

for i, wiersz in enumerate(df.itertuples()):
    sasiedzi = drzewo.query_ball_point([wiersz.x_2180, wiersz.y_2180], r=2000)

    # Bierzemy tylko wczesniejsze transakcje i pomijamy ta, ktora wlasnie liczymy.
    wczesniejsze = [
        j for j in sasiedzi
        if j != i and df.iloc[j]["data_transakcji"] < wiersz.data_transakcji
    ]

    ceny = df.iloc[wczesniejsze]["cena_m2"]
    mediana = ceny.median() if len(ceny) > 0 else None
```

**Test, który trzeba napisać:** cecha policzona dla transakcji z 2020 roku musi być
identyczna przed i po dodaniu do zbioru transakcji z 2021 roku. Jeśli się zmienia,
to znaczy, że model podgląda przyszłość.

### Uwaga o geometrii

Cechy tej grupy wymagają współrzędnych `x_2180` i `y_2180`, a te są tylko w 89,8%
rekordów. Pozostałe 10,2% dostanie `NaN` albo trzeba im najpierw dociągnąć geometrię
(patrz „ULDK" niżej).

## Grupa D — z OpenStreetMap (27 cech, wagi 5–8)

**Źródło: `db/dane/surowe/osm/dolnoslaskie-260913.osm.pbf` — plik już jest na dysku (180 MB).**
**Potrzebne dodatkowo: `pyrosm`, `geopandas`, `scipy`.**

Zawartość pliku (policzona):
```
BUDYNKI              1 286 554 poligonów
LASY                    78 824 poligonów   (landuse=forest + natural=wood)
WODA                    25 055 obiektów
DROGI                  413 000+ odcinków, z podziałem na klasy
MIEJSCOWOŚCI             2 626 punktów     (4 miasta, 95 miasteczek, 2 527 wsi)
   z podaną liczbą mieszkańców: 792
```

To wystarcza, żeby **nie pobierać BDOT10k** — OSM daje wszystkie potrzebne warstwy.

### D1. Zabudowa i urbanizacja (7 cech) — najsilniejsza podgrupa

| Cecha | Tag OSM | Jak policzyć | Waga |
|---|---|---|---|
| `liczba_budynkow_1000m` | `building=*` | `cKDTree.query_ball_point(r=1000)` na środkach budynków | 8 |
| `liczba_budynkow_500m` | `building=*` | To samo, promień 500 m | 8 |
| `czy_w_terenie_zabudowanym` | `landuse=residential` | Czy punkt leży wewnątrz poligonu | 8 |
| `liczba_budynkow_250m` | `building=*` | Promień 250 m | 7 |
| `odl_budynek_mieszkalny_m` | `building` = `house`, `residential`, `apartments`, `detached` | Odległość do najbliższego | 7 |
| `odl_najblizszy_budynek_m` | `building=*` | Odległość do najbliższego | 7 |
| `udzial_zabudowy_500m` | `landuse=residential` | Pole przecięcia z kołem / pole koła | 7 |

### D2. Dostępność komunikacyjna (7 cech)

| Cecha | Tag OSM | Ile w pliku | Waga |
|---|---|---|---|
| `odl_droga_utwardzona_m` | `highway` = `residential`, `unclassified`, `tertiary`, `secondary`, `primary` | 96 565 | 7 |
| `odl_wezel_autostrady_m` | `highway=motorway_junction` | — | 7 |
| `odl_droga_dowolna_m` | `highway=*` bez `footway`, `path`, `steps` | ~413 tys. | 6 |
| `odl_droga_glowna_m` | `highway` = `primary`, `trunk` | 6 460 | 6 |
| `odl_droga_lokalna_m` | `highway=residential` | 50 274 | 6 |
| `odl_autostrada_m` | `highway=motorway` | 2 041 | 5 |
| `odl_przystanek_m` | `highway=bus_stop` | 9 750 | 5 |

> **`highway=track` to drogi polne** (123 322 odcinki w pliku). Trzeba je wykluczyć
> z `odl_droga_dowolna_m`, inaczej cecha przestanie odróżniać dojazd do drogi publicznej
> od zwykłej miedzy.

> **Odległość do autostrady działa dziwnie i to jest ciekawe.** 200 m to hałas, który
> obniża cenę. 5 km to dobry dojazd, który ją podnosi. 50 km to peryferia, gdzie znowu
> jest taniej. Model drzewiasty to wychwyci, model liniowy nie — dobry argument
> w rozdziale o wyborze modelu.

### D3. Położenie względem miast (6 cech)

| Cecha | Jak policzyć | Waga |
|---|---|---|
| `odl_wroclaw_m` | `place=city` o nazwie Wrocław (893 506 mieszkańców) | 8 |
| `odl_miasto_pow_50k_m` | `place` = `city`/`town` z `population > 50000` | 8 |
| `odl_miasto_pow_10k_m` | To samo, próg 10 000 | 7 |
| `ludnosc_najblizszego_miasta` | Tag `population` najbliższego miasta | 6 |
| `odl_najblizsza_miejscowosc_m` | `place` = `city`/`town`/`village` | 6 |
| `odl_granica_panstwa_m` | `boundary=administrative` z `admin_level=2` | 5 |

Największe ośrodki w pliku:
```
Wrocław      893 506      Wałbrzych 104 401      Legnica     94 878
Jelenia Góra  77 305      Lubin      70 016      Głogów      64 261
Görlitz (DE)  57 427      Świdnica   54 792      Bolesławiec 37 559
```

> **Görlitz jest po niemieckiej stronie i to nie jest błąd.** Plik z Geofabrik ma
> kształt prostokąta, więc obejmuje kawałek Niemiec i Czech. Nie filtruj tego —
> Görlitz realnie podnosi ceny działek w Zgorzelcu, tak jak bliskość granicy w całym
> pasie przygranicznym. To prawdziwy sygnał rynkowy.

> **Tylko 792 z 2 626 miejscowości ma podaną liczbę mieszkańców.** Dla miast powyżej
> 10 tysięcy pokrycie jest w praktyce pełne, a to one mają znaczenie. Resztę można
> uzupełnić z GUS (grupa E).

### D4. Środowisko (3 cechy)

| Cecha | Tag OSM | Ile w pliku | Waga |
|---|---|---|---|
| `czy_woda_w_200m` | `natural=water` lub `waterway=river` | 25 055 | 6 |
| `udzial_lasu_500m` | `landuse=forest` lub `natural=wood` | 78 824 | 5 |
| `odl_woda_m` | `natural=water` | 22 721 | 5 |

`udzial_lasu_500m` liczy powierzchnię lasu w kole o promieniu 500 m podzieloną przez
pole koła. To lepsza miara niż odległość do najbliższego skrawka lasu.

### D5. Infrastruktura (4 cechy)

| Cecha | Tag OSM | Waga |
|---|---|---|
| `odl_szkola_m` | `amenity=school` | 6 |
| `odl_sklep_spozywczy_m` | `shop` = `supermarket`, `convenience` | 6 |
| `liczba_poi_1km` | Wszystkie `amenity` i `shop` | 6 |
| `odl_przedszkole_m` | `amenity=kindergarten` | 5 |

> ### ⚠️ Pułapka: obiekty są w OSM zapisane na dwa sposoby
>
> Ten sam obiekt może być punktem albo poligonem. **Trzeba sumować oba źródła:**
>
> | Obiekt | jako punkt | jako poligon | razem |
> |---|---|---|---|
> | szkoła | 380 | 936 | **1 316** |
> | przedszkole | 342 | 519 | **861** |
> | supermarket | 354 | 864 | **1 218** |
> | sklep osiedlowy | 2 124 | 537 | **2 661** |
>
> Czytając same punkty straciłbyś **71% szkół**.

### D6. Jak technicznie czytać plik OSM

```
Biblioteka:  pyrosm (szybsza od osmnx przy dużych plikach)

UWAGA: OSM jest w układzie EPSG:4326 (stopnie), a dane RCN w EPSG:2180 (metry).
       PRZED liczeniem czegokolwiek trzeba przeliczyć:  gdf = gdf.to_crs(2180)
       Odległość liczona w stopniach nie ma sensu.

WYDAJNOŚĆ: 76 tysięcy działek razy 1,29 miliona budynków.
  ŹLE:    pętla po GeoDataFrame            -> godziny
  DOBRZE: scipy.spatial.cKDTree            -> sekundy
          drzewo.query_ball_point(punkty, r=1000, return_length=True)
```

**Wynik parsowania zapisz do pliku pośredniego** (`warstwy_osm.parquet`). Czytanie
180 MB trwa minuty — nie ma sensu robić tego przy każdym uruchomieniu.

## Grupa E — dane o gminach z GUS (8 cech, wagi 5–7)

**Źródło: REST API Banku Danych Lokalnych, `bdl.stat.gov.pl/api/v1/`**
Złączenie po kodzie TERYT gminy. **160 gmin, jedno API, około pół dnia pracy.**

| Cecha | Waga |
|---|---|
| `zmiana_ludnosci_5lat_proc` — czy gmina rośnie czy się wyludnia | 7 |
| `mieszkania_oddane_na_1000` — bezpośrednia miara presji budowlanej | 7 |
| `gestosc_zaludnienia_gmina` | 7 |
| `ludnosc_gminy` | 7 |
| `saldo_migracji_gmina` | 6 |
| `dochody_gminy_per_capita` | 6 |
| `podmioty_gospodarcze_na_1000` | 5 |
| `stopa_bezrobocia_powiat` | 5 |

Te cechy tłumaczą, dlaczego identyczna działka kosztuje inaczej pod Wrocławiem niż pod
Wałbrzychem. Najlepszy stosunek zysku do włożonej pracy spośród źródeł zewnętrznych.

## Uzupełnienie geometrii z ULDK

**7 750 rekordów (10,2%) nie ma geometrii w pliku.** Można ją dociągnąć z usługi GUGiK:

```
https://uldk.gugik.gov.pl/?request=GetParcelById
    &id=021001_1.0005.AR_17.35/2
    &result=geom_wkt,teryt,voivodeship,county,commune,region
```

Jedno zapytanie zwraca geometrię, województwo, powiat, gminę i obręb. Domyślnie
w układzie EPSG:2180.

Zasady: **cache na dysku** (jedno zapytanie na identyfikator, nigdy dwa razy),
spowolnienie do 5–10 zapytań na sekundę, możliwość wznowienia po przerwaniu.
Przy 7 750 rekordach to około 20 minut.

---

# Kolejność dokładania

```
1. Grupa C  — sąsiedztwo cenowe      z tego samego pliku, największy zysk
2. Pierwszy model                     dopiero teraz warto cokolwiek trenować
3. Grupa D  — OpenStreetMap           plik już masz
4. Grupa E  — GUS BDL                 jedno API
5. ULDK                               uzupełnienie brakującej geometrii
```

Każdy krok to jeden nowy plik w katalogu `etl/` i jedna linia w `main.py`.
Nic z tego, co już działa, nie będzie wymagało przepisania.

---

# Cechy odrzucone i dlaczego

## Z wersji 1 — były zaimplementowane, usunięte po weryfikacji

| Cecha | Dlaczego odpadła |
|---|---|
| `kwartal` | Sprawdzone empirycznie na gotowym zbiorze: mediana ceny wg kwartału w obrębie każdego roku osobno nie pokazuje powtarzalnego wzorca (raz najdroższy Q1, raz Q4). Średnio po latach różnica między kwartałami to ~4% — słaby, niestabilny sygnał wobec `miesiace_od_2015`, który i tak łapie trend |
| `teryt_obreb` | Parsowany z `dzi_id_dzialki`, ale nieużywany nigdzie poza jedną linią diagnostyczną. Gmina (160 poziomów) uznana za wystarczającą granulację na potrzeby tej pracy — obręb (~3 500 poziomów) zostaje jako możliwość na później |
| `nr_dzialki` | Parsowany, ale nigdy nieużyty nigdzie w kodzie — sam numer działki (np. `35/2`) to praktycznie losowy identyfikator nadawany przy podziale gruntu, bez wartości predykcyjnej |

## Z wersji 2 — rozważane w planowaniu, nie weszły do listy dołożenia

Poniższe cechy rozważaliśmy i **świadomie odrzuciliśmy** — żeby nie wracać do tematu.

| Cecha | Waga | Dlaczego odpada |
|---|---|---|
| `tran_rodzaj_rynku` | 3 | 47,8% braków w pliku |
| `liczba_wierzcholkow` | 3 | Złożoność kształtu nie przekłada się na cenę |
| `odl_linia_energetyczna_m` | 3 | Wpływ jest realny, ale zbyt rzadki, by pomóc modelowi |
| `tran_kupujacy` | 4 | Kto kupił, nie tłumaczy ceny gruntu |
| `liczba_przeznaczen` | 4 | Sama liczba przeznaczeń nic nie wnosi ponad to, które to są |
| `ma_adres` | 4 | Zastąpione przez `miejscowosc` |
| `obwod_m` | 4 | Używany do policzenia wskaźnika zwartości, ale nie jako cecha |
| `odl_stacja_kolejowa_m` | 4 | Tylko 338 stacji, wpływ marginalny |
| `odl_las_m` | 4 | Zastąpione przez `udzial_lasu_500m`, który jest lepszą miarą |
| `odl_rzeka_m` | 4 | Zastąpione przez `czy_woda_w_200m` |
| `udzial_pol_500m` | 4 | Pokrywa się z `udzial_zabudowy_500m` |
| `odl_przychodnia_m` | 4 | Za rzadkie, by różnicować działki |
| `stosunek_bokow` | 5 | Pokrywa się ze wskaźnikiem zwartości |
| `dlugosc_dluzszego_boku` | 5 | Jak wyżej |
| Czas dojazdu (OSRM) | 8 | Wartościowe, ale wymaga osobnego serwera w kontenerze |
| Nachylenie terenu (NMT) | 5 | Wymaga pobrania i obsługi danych rastrowych |
| Strefa powodziowa | 5 | Wymaga osobnej usługi WFS |
