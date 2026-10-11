# Aktualizacja po uzupelnieniu cech — 04.10.2026

Pozostale cechy zostaly policzone dla wszystkich 16 wojewodztw.
Wynik `polska_pelne_cechy/transakcje.parquet`: **732 702 rekordy, 119 kolumn,
76 kandydatow na wejscia modelu**. Obejmuje 27 OSM, 10 dotychczasowych RCN/lokalizacji,
31 dodanych podstawowych/przeznaczenia oraz 8 sasiedztwa cenowego.

Wzgledem dawnego planu: dodano kategorie wod morskich i flage nieznanej kategorii,
a bledna `ma_mpzp` zastapiono `ma_wpis_przeznaczenia`. Lista nie jest sztucznie
uzupelniona surowymi cenami ani identyfikatorami. Jedna flaga nieznanej kategorii
jest obecnie stala (zero); jej obecnosc sluzy obsludze przyszlych danych, nie
jest dowodem przydatnosci predykcyjnej. 76 kandydatow nie oznacza 76 niezaleznych sygnalow.

Trening: 607 757, test od 2025-01-01: 124 945. Wszystkie wojewodztwa sa w obu
zbiorach. Braki miejscowosci: 560 628; braki median 2 km: 27 500, median 5 km:
3 781. Braki nie usuwaja rekordow; ich obsluga nalezy do treningu modelu.
Definicje i zasady podzialu: [PELNE_CECHY.md](PELNE_CECHY.md).

---

Ponizej zachowany audyt sprzed uzupelnienia, opisujacy plik `polska_cechy_osm`.

# Audyt cech — 04.10.2026

Sprawdzono schemat i kolumny `db/dane/gotowe/polska_cechy_osm/transakcje.parquet`:
732 702 transakcje, 79 kolumn. To audyt dostępności, nie pełna kontrola jakości
OSM ani wybór ostatecznych wejść modelu.

| Grupa | W tabeli | Brakuje z historycznego planu |
|---|---:|---:|
| RCN i geometria: historyczna lista 38 kandydatów | 9 | 29 |
| Województwo: dodatkowy kandydat dla całej Polski | 1 | 0 |
| OSM | 27 | 0 |
| Sąsiedztwo cenowe | 0 | 8 |

79 kolumn = 37 obecnych kandydatów na wejścia + 1 cel (`cena_m2`)
+ 41 kolumn surowych, technicznych i diagnostycznych. Ta klasyfikacja nie
oznacza, że wszystkie 37 zostanie użyte w każdym modelu. Użytkowanie może
służyć do podziału na modele. Kategorie wymagają kodowania dopasowanego na treningu.

Historyczny plan liczył 38 + 27 + 8 = 73 kandydatów; dodanie województwa
daje 74. Nie jest to obietnica 74 niezależnych lub przydatnych cech.
24 kolumny przeznaczenia są rozwinięciem jednego pola źródłowego.

## Istniejące cechy RCN i lokalizacji

| Nazwa z planu | Obecna kolumna |
|---|---|
| `sprzedajacy` | `tran_sprzedajacy` |
| `prawo` | `nier_prawo` |
| `sposob_uzytkowania` | `dzi_sposob_uzyt` |
| `teryt_powiat` | `teryt_powiat` |
| `teryt_gmina` | `teryt_gmina` |
| `rok` | `rok` |
| `x_2180` | `x_2180` |
| `y_2180` | `y_2180` |
| `powierzchnia_m2` | `powierzchnia_m2` |
| Województwo | `teryt_woj` |

## Brakujące cechy podstawowe i geometryczne

- `log_powierzchnia`
- `ma_mpzp`
- `miesiace_od_2015`
- `miejscowosc`
- `wskaznik_zwartosci`

Funkcje są w starych `cechy_podstawowe.py` i `cechy_geometryczne.py`, ale nie
były podłączone do nowego krajowego przepływu. Brakujące wielkości można
policzyć z już zapisanych danych; nie trzeba pobierać map ponownie.

`ma_mpzp` wymaga zmiany definicji: brak wpisu nie dowodzi braku planu,
a decyzja WZ nie jest planem MPZP. Nie należy przenosić starej heurystyki bez poprawki.

## Brakujące 24 kolumny przeznaczenia

To historyczna lista, nie zweryfikowany słownik wszystkich kategorii krajowych.
Źródłowe `dzi_przezn_wmpzp` jest w obecnej tabeli. Wykorzystanie tego pola RCN
nie wymaga dodatkowych danych planistycznych; takich danych nadal nie pobieramy.
Użytkowanie gruntu i przeznaczenie pozostają oddzielnymi pojęciami.
Słownik kodowania należy ustalić jawnie albo dopasować tylko na treningu.

- `przezn_budownictwoMieszkanioweJednorodzinne`
- `przezn_brak_danych`
- `przezn_terenRolniczy`
- `przezn_brakMPZPLubWZ`
- `przezn_terenZabudowyUslugowej`
- `przezn_terenDrogWewnetrznych`
- `przezn_innyNiewymieniony`
- `przezn_terenDrogPublicznych`
- `przezn_budownictwoMieszkanioweWielorodzinne`
- `przezn_terenZabudowyZagrodowejGospodarstwRolnych`
- `przezn_terenObiektowProdukcyjnychSkladowIMagazynow`
- `przezn_terenSportuIRekreacji`
- `przezn_las`
- `przezn_terenZieleniUrzadzonej`
- `przezn_obszarITerenGorniczy`
- `przezn_terenInfrastrukturyTechnicznej`
- `przezn_terenWodPowierzchniowychSrodladowych`
- `przezn_decyzjaWarunkiZabudowy`
- `przezn_terenZieleniObjetyFormaOchronyPrzyrody`
- `przezn_terenOgrodowDzialkowych`
- `przezn_terenObslugiProdukcjiWGospodarstwachRolnych`
- `przezn_terenKomunikacjiWodnejSzlakWodny`
- `przezn_terenRozmieszczeniaDuzcychObiektowHandlowych`
- `przezn_cmentarz`

## Sąsiedztwo do wykonania po podziale trening/test

- `mediana_cena_m2_2km_ten_sam_uzytek`
- `mediana_cena_m2_2km_24m`
- `mediana_cena_m2_5km_24m`
- `mediana_cena_m2_obreb`
- `mediana_cena_m2_gmina`
- `liczba_transakcji_2km_24m`
- `trend_cen_gmina_12m`
- `odl_najblizsza_transakcja_m`

## Obecne cechy OSM

- `odl_najblizszy_budynek_m`
- `liczba_budynkow_250m`
- `liczba_budynkow_500m`
- `liczba_budynkow_1000m`
- `odl_budynek_mieszkalny_m`
- `udzial_zabudowy_500m`
- `czy_w_terenie_zabudowanym`
- `udzial_lasu_500m`
- `odl_woda_m`
- `odl_granica_panstwa_m`
- `odl_droga_dowolna_m`
- `odl_droga_utwardzona_m`
- `odl_droga_glowna_m`
- `odl_droga_lokalna_m`
- `odl_autostrada_m`
- `odl_wezel_autostrady_m`
- `odl_przystanek_m`
- `odl_najblizsza_miejscowosc_m`
- `ludnosc_najblizszego_miasta`
- `odl_miasto_pow_10k_m`
- `odl_miasto_pow_50k_m`
- `odl_wroclaw_m`
- `odl_szkola_m`
- `odl_sklep_spozywczy_m`
- `odl_przedszkole_m`
- `liczba_poi_1km`
- `czy_woda_w_200m`

## Kolumny poza aktualną listą kandydatów

Nie wolno automatycznie brać wszystkich kolumn liczbowych jako wejść modelu.
Ceny `tran_cena_brutto`, `nier_cena_brutto`, `dzi_cena_brutto` ujawniają cel.
Pola VAT również wymagają sprawdzenia znaczenia i dostępności przy wycenie.
Udziały i flagi jakości służą obecnie do przeliczenia celu, filtrów oraz oceny
wyników osobno dla sprzedaży pełnych i częściowych udziałów.

`teryt`, `serwis_rcn`, `tran_przestrzen_nazw`, `tran_wersja_id`, `tran_lokalny_id_iip`, `tran_rodzaj_trans`, `tran_kupujacy`, `tran_rodzaj_rynku`, `tran_vat`, `tran_cena_brutto`, `dok_data`, `nier_rodzaj`, `nier_udzial`, `nier_pow_gruntu`, `nier_cena_brutto`, `nier_vat`, `dzi_id_dzialki`, `dzi_nr_dzialki`, `dzi_cena_brutto`, `dzi_vat`, `dzi_przezn_wmpzp`, `dzi_pow_ewid`, `dzi_adres`, `geometry`, `teryt_obreb`, `status_udzialu`, `status_geometrii`, `zrodlo_powierzchni`, `klucz_transakcji`, `zrodlo_geometrii`, `zrodlo_srodka`, `uldk_pobrano_utc`, `egib_pobrano_utc`, `status_jakosci`, `powody_wstrzymania`, `pole_geom_m2`, `obwod_m`, `udzial_sprzedany`, `ma_srodek`, `cena_przeliczona_z_udzialu`, `do_modelu`.

## Następny pojedynczy etap

Przywrócić cztery jednoznaczne cechy z istniejących danych:
`log_powierzchnia`, `miesiace_od_2015`, `miejscowosc`, `wskaznik_zwartosci`.
Następnie osobno opracować przeznaczenie i flagi braków; nie włączać
starego modelu bez jawnej listy wejść. Ten audyt nie uruchamia obliczeń ani treningu.
