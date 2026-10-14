// Typy danych panelu. Odpowiadają temu, co zwraca backend (backend/api.py).

export type Etap = "dane" | "liczenie" | "wynik"

// Kolory z palety panelu. Każdy ma jedno znaczenie.
export type Kolor =
  | "akcja"
  | "sukces"
  | "spadek"
  | "ostrzezenie"
  | "rynek"
  | "model"
  | "wynik"

export type Punkt = [number, number]

// Pierścienie jednego wielokąta (zewnętrzny i dziury) oraz granica z jednego lub kilku wielokątów.
export type Wielokat = Punkt[][]
export type Granica = Wielokat[]

export type DaneDzialki = {
  identyfikator: string
  // Skąd jest granica: z ewidencji (ULDK) albo narysowana przez użytkownika.
  zrodloGranicy: "uldk" | "rysunek"
  numer: string
  obreb: string
  terytObrebu: string
  gmina: string
  powiat: string
  wojewodztwo: string
  granica: Granica
  srodek: Punkt
  pole: number
  zwartosc: number
  powierzchnia: string
  rodzajGruntu: string
  przeznaczenie: string
  prawo: string
  sprzedajacy: string
  dataWyceny: string
}

// Najczęstsze przeznaczenie i rodzaj gruntu wśród sprzedaży w obrębie (albo w gminie).
export type Podpowiedz = {
  obszar: "obreb" | "gmina"
  przeznaczenie: string
  udzial: number
  liczbaSprzedazy: number
  rodzajGruntu: { kod: string; udzial: number } | null
}

// Opis kroku procesu jest stały, a wynik i czas przychodzą z backendu.
export type KrokProcesu = {
  numer: number
  nazwa: string
  opis: string
  kolor: Kolor
  podkroki: string[]
}

export type WynikKroku = {
  numer: number
  wynik: string
  czas: number
}

// Postęp wyceny: indeks bieżącego kroku i liczba skończonych podkroków.
export type Postep = {
  krok: number
  podkrok: number
  kroki: WynikKroku[]
}

export type Uwaga = {
  tekst: string
  dobrze: boolean
}

export type Wycena = {
  cenaM2: number
  przedzialOd: number
  przedzialDo: number
  pewnosc: string
  model: string
  // Od ilu transakcji w 2 km liczono przedział: 0, 1, 10 albo 30.
  koszyk: number
  uwagi?: Uwaga[]
}

export type WynikModelu = {
  nazwa: string
  cenaM2: number
  mae: number
  rmse: number
  r2: number
}

export type WkladCechy = {
  kod: string
  wklad: number
}

// Rozkład wyceny jednego modelu na cechy. Start + suma wkładów = cena tego modelu.
export type Wyjasnienie = {
  model: string
  start: number
  cena: number
  wklady: WkladCechy[]
}

export type WartoscCechy = number | string | null
export type Cechy = Record<string, WartoscCechy>

export type Transakcja = {
  punkt: Punkt
  cenaM2: number
  data: string
  powierzchnia: number
  rodzaj: string | null
}

export type Sprzedaz = {
  data: string
  cenaM2: number
  cena: number
}

// Statystyki cechy z treningu. Liczby mają kwantyle i korelację, kategorie najczęstsze wartości.
export type StatystykaCechy = {
  mediana: number | null
  braki_procent: number
  min?: number | null
  max?: number | null
  srednia?: number | null
  zera_procent?: number | null
  spearman?: number | null
  liczba_wartosci?: number
  najczestsze?: { wartosc: string; liczba: number; mediana_ceny: number }[]
}

export type MetrykiModelu = {
  nazwa: string
  na_logarytmie: boolean
  mae: number
  rmse: number
  r2: number
  mediana_bledu_procent: number
  czas_sekundy: number
}

// Co wiadomo o wytrenowanych modelach (GET /api/model).
export type OpisModelu = {
  najlepszy: string
  modele: MetrykiModelu[]
  przedzialy: { od_transakcji: number; dol: number; gora: number; mae: number; liczba: number }[]
  // Ważność permutacyjna: o ile zł/m² rośnie MAE po przetasowaniu cechy, osobno dla każdego modelu.
  waznosc: Record<string, Record<string, number>>
  statystyki: Record<string, StatystykaCechy>
  bledyGruntow: Record<string, { mae: number; liczba: number }>
  uczenie: { wiersze: number; przed: string }
  test: { wiersze: number; odrzucone: number; od: string }
  progiCeny: { dol: number; gora: number }
}

export type WynikWyceny = {
  cechy: Cechy
  wycena: Wycena
  modele: WynikModelu[]
  // Wkład cech osobno dla każdego modelu, w tej samej kolejności co modele.
  wyjasnienia: Wyjasnienie[]
  naTle: { obszar: "gmina" | "powiat"; percentyle: Record<string, number | null> }
  transakcje: Transakcja[]
  poprzednie: Sprzedaz[]
  kroki: WynikKroku[]
  czas: number
}

// Odpowiedź trybu „co jeśli”: te same modele na zmienionych cechach.
export type Przeliczenie = {
  wycena: Wycena
  modele: WynikModelu[]
  wyjasnienia: Wyjasnienie[]
}

// Grupa wyznacza kolor cechy, rozdział jej miejsce w opisie cech.
export type GrupaCechy = "sasiedztwo" | "osm" | "dzialka" | "przeznaczenie"
export type RozdzialCech = "sasiedztwo" | "transakcja" | "lokalizacja" | "polozenie" | "czas" | "osm" | "przeznaczenie"

export type OpisCechy = {
  kod: string
  nazwa: string
  grupa: GrupaCechy
  rozdzial: RozdzialCech
  jednostka: string
  coTo: string
  poCo: string
  // Jak liczona, krok po kroku.
  kroki: string[]
  wzor?: string
  zrodlo: string
  // Plik i funkcja: w ETL (trening) i w serwerze wyceny (panel).
  etl: string
  panel: string
  uwagi?: string
}

