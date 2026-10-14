// Słownik cech modelu: szczegółowy opis każdej z 54 cech wariantu „formularz”.
// Treść na podstawie praca/OPIS_CECH.md. Statystyki i ważność przychodzą z backendu (/api/model).

import type { GrupaCechy, OpisCechy, RozdzialCech } from "@/typy"
import { PRZEZNACZENIA } from "./slowniki"

export const ROZDZIALY: { kod: RozdzialCech; nazwa: string; opis: string }[] = [
  {
    kod: "sasiedztwo",
    nazwa: "Sąsiedztwo cenowe",
    opis: "Ceny wcześniejszych sprzedaży w okolicy. Tak samo wycenia rzeczoznawca w podejściu porównawczym.",
  },
  {
    kod: "transakcja",
    nazwa: "Transakcja i prawo",
    opis: "Kto sprzedaje, jakie prawo do gruntu i jaki to rodzaj gruntu. Przy wycenie z formularza.",
  },
  {
    kod: "lokalizacja",
    nazwa: "Lokalizacja administracyjna",
    opis: "Województwo, powiat i gmina wycięte z identyfikatora działki.",
  },
  {
    kod: "polozenie",
    nazwa: "Położenie i kształt",
    opis: "Środek, powierzchnia i kształt działki policzone z jej granicy.",
  },
  {
    kod: "czas",
    nazwa: "Czas",
    opis: "Kiedy była sprzedaż, a przy wycenie: data wyceny.",
  },
  {
    kod: "osm",
    nazwa: "Otoczenie z OpenStreetMap",
    opis: "Odległości do dróg, zabudowy, usług i miast oraz gęstość zabudowy wokół działki.",
  },
  {
    kod: "przeznaczenie",
    nazwa: "Przeznaczenie",
    opis: "Flagi 0/1 z pola przeznaczenia w RCN. Przy wycenie z wyboru w formularzu.",
  },
]

const KOLOR_ROZDZIALU: Record<RozdzialCech, GrupaCechy> = {
  sasiedztwo: "sasiedztwo",
  transakcja: "dzialka",
  lokalizacja: "dzialka",
  polozenie: "dzialka",
  czas: "dzialka",
  osm: "osm",
  przeznaczenie: "przeznaczenie",
}

const RCN = "Rejestr cen nieruchomości (RCN)"
const OSM = "OpenStreetMap, ekstrakt Polski z 30.09.2026"
const UWAGA_OSM_CZAS =
  "OSM opisuje stan z 2026 roku, a transakcje sięgają 2015 roku. Okolica w chwili sprzedaży mogła wyglądać inaczej."
const KROK_WARSTWA = (warstwa: string, tagi: string) =>
  `Warstwa OSM „${warstwa}” (${tagi}) przeliczona z EPSG:4326 na EPSG:2180 i zapisana w PostGIS jako dane.osm_${warstwa}.`
const KROK_SRODEK = "Środek działki to centroid jej granicy w układzie EPSG:2180, w metrach."
const SASIEDZTWO_ZASADY = [
  "Tylko sprzedaże ze ściśle wcześniejszego dnia niż data wyceny. Transakcje z tego samego dnia się nie liczą.",
  "Wcześniejsze sprzedaże tej samej działki są pomijane, żeby model nie dostał jej własnej ceny.",
]
const ETL_SASIEDZTWO = "etl/etap6_cechy/sasiedztwo.py · dodaj_sasiedztwo"
const ETL_POZOSTALE = "etl/etap6_cechy/cechy_dzialki.py · dodaj_pozostale"
const ETL_CZYSZCZENIE = "etl/etap2_4_czyszczenie/czyszczenie.py · oczysc"

type Tresc = Omit<OpisCechy, "kod" | "nazwa" | "grupa" | "rozdzial" | "jednostka">

function cecha(kod: string, nazwa: string, rozdzial: RozdzialCech, jednostka: string, tresc: Tresc): OpisCechy {
  return { kod, nazwa, rozdzial, grupa: KOLOR_ROZDZIALU[rozdzial], jednostka, ...tresc }
}

// Odległość od środka działki do najbliższego obiektu warstwy OSM.
function odleglosc(kod: string, nazwa: string, warstwa: string, tagi: string, coTo: string, poCo: string, uwagi?: string) {
  return cecha(kod, nazwa, "osm", "m", {
    coTo,
    poCo,
    kroki: [
      KROK_WARSTWA(warstwa, tagi),
      KROK_SRODEK,
      "Najbliższy obiekt warstwy wyszukiwany przez indeks przestrzenny (GiST, operator <->).",
      "Odległość mierzona do linii albo krawędzi obszaru, nie do jego środka. Środek wewnątrz obszaru daje 0 m.",
    ],
    wzor: "d = min odległość(środek działki, obiekt warstwy)",
    zrodlo: `${OSM} · metry`,
    etl: "etl/etap5_osm/cechy_osm.py · odleglosci_do_geometrii (shapely STRtree)",
    panel: "backend/wycena/cechy.py · odleglosc (PostGIS ST_Distance)",
    uwagi: uwagi ?? UWAGA_OSM_CZAS,
  })
}

// Liczba obiektów OSM, których środki leżą w promieniu od środka działki.
function wPromieniu(kod: string, nazwa: string, warstwa: string, tagi: string, promien: number, coTo: string, poCo: string, uwagi?: string) {
  return cecha(kod, nazwa, "osm", "", {
    coTo,
    poCo,
    kroki: [
      KROK_WARSTWA(warstwa, tagi),
      "Każdy obiekt reprezentuje jego centroid (środek obrysu).",
      KROK_SRODEK,
      `Liczone są obiekty, których środek leży nie dalej niż ${promien} m od środka działki.`,
    ],
    wzor: `n = liczba obiektów z (x − x₀)² + (y − y₀)² ≤ ${promien}²`,
    zrodlo: `${OSM} · liczba obiektów`,
    etl: "etl/etap5_osm/cechy_osm.py · policz_osm (scipy cKDTree.query_ball_point)",
    panel: "backend/wycena/cechy.py · liczba_w_promieniu (PostGIS)",
    uwagi: uwagi ?? UWAGA_OSM_CZAS,
  })
}

// Udział koła 500 m wokół działki zajęty przez obszary warstwy.
function udzialW500(kod: string, nazwa: string, warstwa: string, tagi: string, coTo: string, poCo: string) {
  return cecha(kod, nazwa, "osm", "", {
    coTo,
    poCo,
    kroki: [
      KROK_WARSTWA(warstwa, tagi),
      KROK_SRODEK,
      "Wokół środka powstaje koło o promieniu 500 m (bufor z 16 odcinkami na ćwiartkę).",
      "Obszary warstwy przecinane są z kołem, a części nakładające się liczone tylko raz (suma obszarów).",
      "Pole części wspólnej dzielone jest przez pole koła i obcinane do przedziału 0–1.",
    ],
    wzor: "udział = pole(⋃ obszary ∩ koło 500 m) / pole(koła 500 m)",
    zrodlo: `${OSM} · od 0 do 1`,
    etl: "etl/etap5_osm/cechy_osm.py · udzial_w_kole (shapely buffer, union_all)",
    panel: "backend/wycena/cechy.py · pokrycie (PostGIS ST_Buffer, ST_Union)",
    uwagi: UWAGA_OSM_CZAS,
  })
}

const SASIEDZTWO: OpisCechy[] = [
  cecha("mediana_cena_m2_2km_ten_sam_uzytek", "Mediana 2 km, ten sam użytek", "sasiedztwo", "zł/m²", {
    coTo: "Mediana ceny za m² sprzedaży w promieniu 2 km z ostatnich 24 miesięcy, tylko dla tego samego rodzaju gruntu.",
    poCo: "Najbardziej bezpośrednie porównanie: grunt rolny z gruntem rolnym, budowlany z budowlanym. Najsilniej związana z ceną spośród wszystkich cech.",
    kroki: [
      ...SASIEDZTWO_ZASADY,
      "Wybór sprzedaży w promieniu 2 km od środka działki i w oknie 24 miesięcy przed datą wyceny.",
      "Zostają tylko sprzedaże z tym samym, niepustym rodzajem gruntu.",
      "Mediana ich cen za m². Brak takich sprzedaży daje pustą wartość.",
    ],
    wzor: "mediana{ cena_m2 : odległość ≤ 2 km, data ∈ [wycena − 24 mies., wycena), ten sam użytek }",
    zrodlo: `${RCN} · zł/m²`,
    etl: ETL_SASIEDZTWO,
    panel: "backend/wycena/cechy.py · ceny_w_promieniu",
    uwagi: "Przy rzadkim rynku często pusta. Model dostaje wtedy medianę z treningu i wskaźnik braku.",
  }),
  cecha("mediana_cena_m2_2km_24m", "Mediana 2 km", "sasiedztwo", "zł/m²", {
    coTo: "Mediana ceny za m² wszystkich sprzedaży w promieniu 2 km z ostatnich 24 miesięcy, bez względu na rodzaj gruntu.",
    poCo: "Poziom cen najbliższej okolicy. Rzadziej pusta niż mediana dla tego samego użytku.",
    kroki: [
      ...SASIEDZTWO_ZASADY,
      "Wybór sprzedaży w promieniu 2 km i w oknie 24 miesięcy przed datą wyceny.",
      "Mediana ich cen za m².",
    ],
    wzor: "mediana{ cena_m2 : odległość ≤ 2 km, data ∈ [wycena − 24 mies., wycena) }",
    zrodlo: `${RCN} · zł/m²`,
    etl: ETL_SASIEDZTWO,
    panel: "backend/wycena/cechy.py · ceny_w_promieniu",
  }),
  cecha("mediana_cena_m2_5km_24m", "Mediana 5 km", "sasiedztwo", "zł/m²", {
    coTo: "Mediana ceny za m² sprzedaży w promieniu 5 km z ostatnich 24 miesięcy.",
    poCo: "Szersze tło rynku. Prawie zawsze dostępna, także tam, gdzie w 2 km nic nie sprzedano.",
    kroki: [
      ...SASIEDZTWO_ZASADY,
      "Wybór sprzedaży w promieniu 5 km i w oknie 24 miesięcy przed datą wyceny.",
      "Mediana ich cen za m².",
    ],
    wzor: "mediana{ cena_m2 : odległość ≤ 5 km, data ∈ [wycena − 24 mies., wycena) }",
    zrodlo: `${RCN} · zł/m²`,
    etl: ETL_SASIEDZTWO,
    panel: "backend/wycena/cechy.py · ceny_w_promieniu",
  }),
  cecha("mediana_cena_m2_obreb", "Mediana w obrębie", "sasiedztwo", "zł/m²", {
    coTo: "Mediana ceny za m² wszystkich wcześniejszych sprzedaży w tym samym obrębie ewidencyjnym, bez limitu czasu.",
    poCo: "Obręb to zwykle jedna wieś albo część miasta, więc dobrze opisuje lokalny rynek.",
    kroki: [
      ...SASIEDZTWO_ZASADY,
      "Obręb z identyfikatora działki, np. 126102_9.0001.",
      "Mediana cen wszystkich wcześniejszych sprzedaży w obrębie, od 2015 roku.",
    ],
    wzor: "mediana{ cena_m2 : ten sam obręb, data < wycena }",
    zrodlo: `${RCN} · zł/m²`,
    etl: ETL_SASIEDZTWO,
    panel: "backend/wycena/cechy.py · ceny_w_obszarze",
    uwagi: "Bez limitu czasu, więc w obrębach z niewieloma sprzedażami miesza stare i nowe ceny.",
  }),
  cecha("mediana_cena_m2_gmina", "Mediana w gminie", "sasiedztwo", "zł/m²", {
    coTo: "Mediana ceny za m² wszystkich wcześniejszych sprzedaży w tej samej gminie, bez limitu czasu.",
    poCo: "Ogólny poziom cen gminy. Dostępna prawie zawsze.",
    kroki: [
      ...SASIEDZTWO_ZASADY,
      "Gmina z identyfikatora działki (siedem znaków z cyfrą rodzaju gminy).",
      "Mediana cen wszystkich wcześniejszych sprzedaży w gminie.",
    ],
    wzor: "mediana{ cena_m2 : ta sama gmina, data < wycena }",
    zrodlo: `${RCN} · zł/m²`,
    etl: ETL_SASIEDZTWO,
    panel: "backend/wycena/cechy.py · ceny_w_obszarze",
  }),
  cecha("liczba_transakcji_2km_24m", "Transakcje w 2 km", "sasiedztwo", "", {
    coTo: "Liczba sprzedaży, z których policzono medianę 2 km: promień 2 km, ostatnie 24 miesiące.",
    poCo: "Mówi, jak pewne są ceny z okolicy. Od niej zależy też szerokość przedziału 80% w panelu.",
    kroki: [...SASIEDZTWO_ZASADY, "Liczba sprzedaży w promieniu 2 km i w oknie 24 miesięcy. Brak sprzedaży to 0, nie pusta wartość."],
    wzor: "n = liczba{ sprzedaże : odległość ≤ 2 km, data ∈ [wycena − 24 mies., wycena) }",
    zrodlo: `${RCN} · liczba`,
    etl: ETL_SASIEDZTWO,
    panel: "backend/wycena/cechy.py · ceny_w_promieniu",
  }),
  cecha("trend_cen_gmina_12m", "Trend cen w gminie", "sasiedztwo", "", {
    coTo: "Jak zmieniła się mediana ceny w gminie w ostatnim roku względem roku wcześniejszego. 0,1 oznacza wzrost o 10%.",
    poCo: "Kierunek rynku: czy ceny w okolicy rosną, czy spadają.",
    kroki: [
      ...SASIEDZTWO_ZASADY,
      "Mediana cen w gminie z ostatnich 12 miesięcy przed datą wyceny.",
      "Mediana z 12 miesięcy wcześniejszych (od 24 do 12 miesięcy przed wyceną).",
      "Iloraz minus 1. Wymaga co najmniej jednej sprzedaży w każdym z okien.",
    ],
    wzor: "trend = mediana(ostatnie 12 mies.) / mediana(12 mies. wcześniej) − 1",
    zrodlo: `${RCN} · ułamek`,
    etl: ETL_SASIEDZTWO,
    panel: "backend/wycena/cechy.py · ceny_w_obszarze",
    uwagi: "Niestabilny w małych gminach: kilka sprzedaży potrafi zmienić go o kilkadziesiąt procent.",
  }),
  cecha("odl_najblizsza_transakcja_m", "Odległość do transakcji", "sasiedztwo", "m", {
    coTo: "Odległość od środka działki do środka najbliższej wcześniejszej sprzedaży, bez limitu czasu i promienia.",
    poCo: "Mówi, jak daleko trzeba sięgnąć po porównanie. Duża odległość to rzadki rynek.",
    kroki: [...SASIEDZTWO_ZASADY, "Najbliższa wcześniejsza sprzedaż wyszukiwana przez indeks przestrzenny środków transakcji."],
    wzor: "d = min odległość(środek działki, środek wcześniejszej sprzedaży)",
    zrodlo: `${RCN} · metry`,
    etl: ETL_SASIEDZTWO,
    panel: "backend/wycena/cechy.py · najblizsza_transakcja",
  }),
]

const FORMULARZ_PRZY_WYCENIE = "backend/wycena/cechy.py · cechy_formularza (z formularza)"

const TRANSAKCJA: OpisCechy[] = [
  cecha("tran_sprzedajacy", "Kto sprzedaje", "transakcja", "", {
    coTo: "Osoba fizyczna, firma, gmina albo Skarb Państwa.",
    poCo: "Sprzedaż przez firmę, gminę albo Skarb Państwa to inny rynek niż sprzedaż między osobami: przetargi, działki inwestycyjne, grunty z zasobu państwa.",
    kroki: [
      "W treningu: kolumna RCN tran_sprzedajacy, bez zmian.",
      "W modelu: każda kategoria dostaje kolumnę 0/1, brak to osobna kategoria __BRAK__.",
      "Przy wycenie: wybór w formularzu.",
    ],
    zrodlo: "RCN (trening) · formularz (wycena)",
    etl: ETL_CZYSZCZENIE,
    panel: FORMULARZ_PRZY_WYCENIE,
  }),
  cecha("nier_prawo", "Prawo do gruntu", "transakcja", "", {
    coTo: "Własność albo użytkowanie wieczyste.",
    poCo: "Użytkowanie wieczyste i własność mają inną wartość. Użytkowanie wieczyste występuje głównie w miastach.",
    kroki: [
      "W treningu: kolumna RCN nier_prawo, bez zmian.",
      "W modelu: kolumny 0/1 dla kategorii.",
      "Przy wycenie: wybór w formularzu (dwie najczęstsze kategorie).",
    ],
    zrodlo: "RCN (trening) · formularz (wycena)",
    etl: ETL_CZYSZCZENIE,
    panel: FORMULARZ_PRZY_WYCENIE,
    uwagi: "W RCN są też nieliczne wpisy „własność budynku” i „własność lokalu” przy gruncie niezabudowanym. To niespójność rejestru.",
  }),
  cecha("dzi_sposob_uzyt", "Rodzaj gruntu", "transakcja", "", {
    coTo: "Sposób użytkowania z ewidencji: grunty rolne, zabudowane i zurbanizowane, leśne, komunikacyjne lub inne.",
    poCo: "Najsilniejszy podział rynku: mediany cen różnią się kilkunastokrotnie między gruntami leśnymi a zabudowanymi.",
    kroki: [
      "W treningu: kolumna RCN dzi_sposob_uzyt, bez zmian.",
      "W modelu: kolumny 0/1 dla kategorii. Wyznacza też „ten sam użytek” w medianie 2 km.",
      "Przy wycenie: wybór w formularzu, z podpowiedzią najczęstszego rodzaju w obrębie.",
    ],
    zrodlo: "RCN (trening) · formularz (wycena)",
    etl: ETL_CZYSZCZENIE,
    panel: FORMULARZ_PRZY_WYCENIE,
  }),
]

const KROK_TERYT = "Kody wycinane z identyfikatora działki wzorcem WWPPGG_R.OOOO.numer, np. 126102_9.0001.100/1."

const LOKALIZACJA: OpisCechy[] = [
  cecha("teryt_woj", "Województwo", "lokalizacja", "", {
    coTo: "Kod województwa, np. 12 to małopolskie.",
    poCo: "Najszerszy poziom różnic regionalnych w cenach.",
    kroki: [KROK_TERYT, "Województwo to dwie pierwsze cyfry.", "W modelu: kolumny 0/1 dla 16 województw."],
    zrodlo: "Identyfikator działki · TERYT",
    etl: ETL_CZYSZCZENIE,
    panel: FORMULARZ_PRZY_WYCENIE,
  }),
  cecha("teryt_powiat", "Powiat", "lokalizacja", "", {
    coTo: "Kod powiatu: cztery pierwsze cyfry identyfikatora, np. 1261 to Kraków.",
    poCo: "Odróżnia powiat podmiejski od peryferyjnego w tym samym województwie.",
    kroki: [
      KROK_TERYT,
      "Powiat to cztery pierwsze cyfry.",
      "W modelu kodowanie średnią celu: powiat zamieniany jest na średnią (log-)ceny jego sprzedaży z treningu, liczoną krzyżowo w 5 częściach, żeby wiersz nie widział własnej ceny.",
    ],
    zrodlo: "Identyfikator działki · TERYT",
    etl: ETL_CZYSZCZENIE,
    panel: FORMULARZ_PRZY_WYCENIE,
    uwagi: "Powiat nieobecny w treningu dostaje średnią całego zbioru.",
  }),
  cecha("teryt_gmina", "Gmina", "lokalizacja", "", {
    coTo: "Kod gminy: sześć cyfr i cyfra rodzaju gminy, np. 1261029.",
    poCo: "Najdokładniejszy podział administracyjny w modelu.",
    kroki: [
      KROK_TERYT,
      "Gmina to sześć cyfr i cyfra po podkreślniku.",
      "W modelu kodowanie średnią celu, jak dla powiatu. Zamiast 2,5 tys. kolumn 0/1 jest jedna liczba.",
    ],
    zrodlo: "Identyfikator działki · TERYT",
    etl: ETL_CZYSZCZENIE,
    panel: FORMULARZ_PRZY_WYCENIE,
    uwagi: "Gmina nieobecna w treningu dostaje średnią całego zbioru.",
  }),
]

const POLOZENIE: OpisCechy[] = [
  cecha("x_2180", "Współrzędna X środka", "polozenie", "m", {
    coTo: "Położenie środka działki z zachodu na wschód w układzie PUWG 1992 (EPSG:2180).",
    poCo: "Pozwala modelom drzewiastym wydzielić obszary o podobnych cenach bez nazw miejscowości.",
    kroki: ["Granica działki przeliczona na EPSG:2180.", "Centroid granicy, współrzędna X w metrach."],
    zrodlo: "Granica z RCN, EGiB lub ULDK · metry",
    etl: "etl/etap2_4_czyszczenie/geometria.py · dodaj_geometrie",
    panel: "backend/wycena/cechy.py · cechy_granicy (PostGIS ST_Centroid)",
  }),
  cecha("y_2180", "Współrzędna Y środka", "polozenie", "m", {
    coTo: "Położenie środka działki z południa na północ w układzie PUWG 1992 (EPSG:2180).",
    poCo: "Razem ze współrzędną X opisuje położenie działki w kraju.",
    kroki: ["Granica działki przeliczona na EPSG:2180.", "Centroid granicy, współrzędna Y w metrach."],
    zrodlo: "Granica z RCN, EGiB lub ULDK · metry",
    etl: "etl/etap2_4_czyszczenie/geometria.py · dodaj_geometrie",
    panel: "backend/wycena/cechy.py · cechy_granicy (PostGIS ST_Centroid)",
  }),
  cecha("powierzchnia_m2", "Powierzchnia", "polozenie", "m²", {
    coTo: "Powierzchnia działki w m².",
    poCo: "Większe działki mają niższą cenę za metr. Jedna z najsilniejszych cech.",
    kroki: [
      "W treningu: powierzchnia z ewidencji potwierdzona polem z granicy (tolerancja 0,80–1,25, z rozpoznaniem hektarów).",
      "Do modelu trafiają działki od 100 do 200 000 m².",
      "Przy wycenie: wartość z formularza, domyślnie pole z granicy ULDK. Można ją poprawić.",
    ],
    zrodlo: "Ewidencja i granica · m²",
    etl: "etl/etap2_4_czyszczenie/geometria.py · ustal_powierzchnie",
    panel: FORMULARZ_PRZY_WYCENIE,
    uwagi: "Poza zakresem 100–200 000 m² model nie miał przykładów i panel pokazuje ostrzeżenie.",
  }),
  cecha("log_powierzchnia", "Logarytm powierzchni", "polozenie", "", {
    coTo: "Powierzchnia w skali logarytmicznej.",
    poCo: "Różnica 500 i 1000 m² znaczy więcej niż 50 000 i 50 500 m². Pomaga modelom liniowym; drzewom nic nie zmienia.",
    kroki: ["Logarytm naturalny powierzchni w m².", "W trybie „co jeśli” liczony automatycznie z powierzchni."],
    wzor: "log_powierzchnia = ln(powierzchnia_m2)",
    zrodlo: "Pochodna powierzchni",
    etl: ETL_POZOSTALE,
    panel: FORMULARZ_PRZY_WYCENIE,
  }),
  cecha("wskaznik_zwartosci", "Wskaźnik zwartości", "polozenie", "", {
    coTo: "Jak bardzo kształt działki przypomina koło: 1 to koło, wartości bliskie 0 to wąski pas.",
    poCo: "Wąski pas jest trudny do zabudowy i typowy dla gruntów rolnych albo dróg. Kształt zbliżony do kwadratu jest typowy dla działek budowlanych.",
    kroki: ["Pole i obwód granicy w EPSG:2180 (obwód obejmuje też brzegi otworów).", "Stosunek pola do pola koła o tym samym obwodzie."],
    wzor: "zwartość = 4π · pole / obwód²",
    zrodlo: "Granica z RCN, EGiB lub ULDK · od 0 do 1",
    etl: ETL_POZOSTALE,
    panel: "backend/wycena/cechy.py · cechy_granicy",
    uwagi: "Jak czytać: koło 1, kwadrat 0,785, prostokąt 1:2 0,698, prostokąt 1:10 0,260, pas 1:50 0,060.",
  }),
]

const CZAS: OpisCechy[] = [
  cecha("rok", "Rok", "czas", "", {
    coTo: "Rok sprzedaży, a przy wycenie rok daty wyceny.",
    poCo: "Ogólny poziom cen w danym roku.",
    kroki: ["Rok z daty aktu notarialnego (dok_data).", "Przy wycenie: rok z daty w formularzu."],
    zrodlo: "RCN (trening) · formularz (wycena)",
    etl: ETL_CZYSZCZENIE,
    panel: FORMULARZ_PRZY_WYCENIE,
  }),
  cecha("miesiace_od_2015", "Miesiące od 2015", "czas", "", {
    coTo: "Liczba miesięcy od stycznia 2015: styczeń 2015 = 0, grudzień 2024 = 119.",
    poCo: "Dokładniejsza oś czasu niż sam rok, do uchwycenia trendu cen.",
    kroki: ["Rok i miesiąc z daty sprzedaży albo daty wyceny."],
    wzor: "miesiące = (rok − 2015) · 12 + miesiąc − 1",
    zrodlo: "RCN (trening) · formularz (wycena)",
    etl: ETL_POZOSTALE,
    panel: FORMULARZ_PRZY_WYCENIE,
    uwagi: "Daty po 2024 roku leżą poza treningiem. Drzewa przyjmą poziom z końca treningu, model liniowy przedłuży trend. Aktualny poziom cen niosą głównie cechy sąsiedztwa.",
  }),
]

const OTOCZENIE: OpisCechy[] = [
  odleglosc("odl_najblizszy_budynek_m", "Odległość do budynku", "budynki", "building=* oprócz no",
    "Odległość od środka działki do najbliższego budynku dowolnego typu.",
    "Bliskość zabudowy oznacza zwykle dostęp do mediów i drogi oraz grunt bliższy budowlanemu. Najsilniej związana z ceną spośród cech OSM.",
    "Zero przy działce sprzedanej jako niezabudowana zwykle oznacza budynek postawiony po sprzedaży: OSM jest z 2026 roku. To częściowy przeciek informacji z przyszłości."),
  wPromieniu("liczba_budynkow_1000m", "Budynki w 1 km", "budynki", "building=* oprócz no", 1000,
    "Liczba budynków w promieniu 1 km od środka działki.",
    "Skala całej miejscowości wokół działki."),
  udzialW500("udzial_lasu_500m", "Las w 500 m", "las", "landuse=forest lub natural=wood",
    "Jaka część koła 500 m wokół działki to las.",
    "Las w pobliżu może podnosić cenę działek rekreacyjnych, a obniżać rolnych. Zależność nie jest monotoniczna, więc wykorzystają ją głównie drzewa."),
  odleglosc("odl_droga_dowolna_m", "Odległość do drogi", "drogi", "highway=* bez track, path, footway, cycleway, steps i podobnych",
    "Odległość do najbliższej drogi kołowej, bez dróg polnych, ścieżek i chodników.",
    "Dostęp do drogi. Wykluczenie dróg polnych jest kluczowe, bo są niemal wszędzie."),
  odleglosc("odl_droga_utwardzona_m", "Odległość do drogi utwardzonej", "utwardzone", "drogi z surface = asphalt, concrete, paving_stones, sett, paved",
    "Odległość do najbliższej drogi o jawnie utwardzonej nawierzchni.",
    "Dojazd drogą utwardzoną.",
    "Wymaga tagu surface: droga asfaltowa bez tego tagu nie trafia do warstwy. Cecha mierzy więc też kompletność opisu OSM."),
  odleglosc("odl_miasto_pow_50k_m", "Odległość do miasta 50 tys.+", "miasta_50k", "miasta z population > 50 000",
    "Odległość do najbliższego miasta powyżej 50 tys. mieszkańców.",
    "Dojazd do dużego rynku pracy."),
  wPromieniu("liczba_poi_1km", "Usługi w 1 km", "poi", "każdy amenity=* lub shop=*", 1000,
    "Liczba obiektów usługowych w promieniu 1 km: sklepów, szkół, przychodni, restauracji i innych.",
    "Ogólna „miejskość” okolicy.",
    "Ten sam obiekt bywa w OSM punktem i obszarem naraz, więc może być policzony dwa razy."),
]

function przeznaczenia(): OpisCechy[] {
  const lista: OpisCechy[] = []
  for (const grupa of PRZEZNACZENIA) {
    for (const opcja of grupa.opcje) {
      const nazwa = opcja.nazwa.toLowerCase()
      lista.push(
        cecha(`przezn_${opcja.kod}`, `Przeznaczenie: ${nazwa}`, "przeznaczenie", "", {
          coTo: `Czy plan miejscowy lub decyzja WZ przewiduje na działce: ${nazwa} (1 = tak).`,
          poCo: "Przeznaczenie decyduje o tym, czy można budować. Działka budowlana i rolna w tym samym miejscu różnią się wielokrotnie.",
          kroki: [
            "W treningu: pole RCN dzi_przezn_wmpzp dzielone po średniku. Wpis może mieć kilka kategorii naraz.",
            `Flaga 1, gdy wśród kategorii jest „${opcja.kod}”, w przeciwnym razie 0.`,
            "Przy wycenie: dokładnie jedna kategoria z formularza.",
          ],
          zrodlo: "RCN (trening) · formularz (wycena)",
          etl: ETL_POZOSTALE,
          panel: FORMULARZ_PRZY_WYCENIE,
          uwagi: "To informacja zapisana w RCN przy sprzedaży, a nie potwierdzenie obowiązującego planu.",
        })
      )
    }
  }
  lista.push(
    cecha("przezn_brak_danych", "Brak wpisu przeznaczenia", "przeznaczenie", "", {
      coTo: "Czy pole przeznaczenia w RCN jest puste. To brak informacji, a nie brak planu.",
      poCo: "Odróżnia transakcje bez żadnej informacji o planie od tych z wpisem.",
      kroki: ["W treningu: 1, gdy pole przeznaczenia jest puste.", "Przy wycenie zawsze 0, bo przeznaczenie jest wymagane."],
      zrodlo: "RCN (trening) · formularz (wycena)",
      etl: ETL_POZOSTALE,
      panel: FORMULARZ_PRZY_WYCENIE,
      uwagi: "Dokładne przeciwieństwo „Ma wpis przeznaczenia”, więc jedna z tych cech jest nadmiarowa.",
    }),
    cecha("ma_wpis_przeznaczenia", "Ma wpis przeznaczenia", "przeznaczenie", "", {
      coTo: "Czy dla działki jest jakikolwiek wpis przeznaczenia, także wpis o braku planu.",
      poCo: "Wpis częściej pojawia się na aktywnych rynkach budowlanych.",
      kroki: ["W treningu: 1, gdy pole przeznaczenia nie jest puste.", "Przy wycenie zawsze 1."],
      zrodlo: "RCN (trening) · formularz (wycena)",
      etl: ETL_POZOSTALE,
      panel: FORMULARZ_PRZY_WYCENIE,
    })
  )
  return lista
}

export const OPISY_CECH: OpisCechy[] = [
  ...SASIEDZTWO,
  ...TRANSAKCJA,
  ...LOKALIZACJA,
  ...POLOZENIE,
  ...CZAS,
  ...OTOCZENIE,
  ...przeznaczenia(),
]

export function opisCechy(kod: string): OpisCechy {
  const opis = OPISY_CECH.find((o) => o.kod === kod)
  if (opis) {
    return opis
  }
  return cecha(kod, kod, "polozenie", "", { coTo: "Cecha modelu.", poCo: "", kroki: [], zrodlo: "—", etl: "—", panel: "—" })
}

// Cechy z listą wartości zamiast liczby oraz cechy wyliczane z innych.
// Tych nie da się zmienić w trybie „co jeśli”; logarytm backend liczy z powierzchni.
export const KATEGORIE = ["tran_sprzedajacy", "nier_prawo", "dzi_sposob_uzyt", "teryt_woj", "teryt_powiat", "teryt_gmina"]
export const TYLKO_DO_ODCZYTU = [...KATEGORIE, "log_powierzchnia"]
