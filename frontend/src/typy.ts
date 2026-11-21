export type Etap = "dane" | "liczenie" | "wynik"

export type Kolor =
  | "akcja"
  | "sukces"
  | "spadek"
  | "ostrzezenie"
  | "rynek"
  | "model"
  | "wynik"

export type Punkt = [number, number]

export type Wielokat = Punkt[][]
export type Granica = Wielokat[]

export type DaneDzialki = {
  identyfikator: string
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

export type Podpowiedz = {
  obszar: "obreb" | "gmina"
  przeznaczenie: string
  udzial: number
  liczbaSprzedazy: number
  rodzajGruntu: { kod: string; udzial: number } | null
}

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

export type StatystykaCechy = {
  min: number
  mediana: number
  max: number
  srednia: number
}

export type MetrykiModelu = {
  nazwa: string
  mae: number
  rmse: number
  r2: number
  mediana_bledu_procent: number
  czas_sekundy: number
}

export type OpisModelu = {
  najlepszy: string
  modele: MetrykiModelu[]
  przedzialy: { od_transakcji: number; dol: number; gora: number; mae: number; liczba: number }[]
  waznosc: Record<string, Record<string, number>>
  statystyki: Record<string, StatystykaCechy>
  uczenie: { wiersze: number; przed: string }
  test: { wiersze: number; odrzucone: number; od: string }
  progiCeny: { dol: number; gora: number }
}

export type WynikWyceny = {
  cechy: Cechy
  wycena: Wycena
  modele: WynikModelu[]
  wyjasnienia: Wyjasnienie[]
  naTle: { obszar: "gmina" | "powiat"; percentyle: Record<string, number | null> }
  transakcje: Transakcja[]
  poprzednie: Sprzedaz[]
  kroki: WynikKroku[]
  czas: number
}

export type Przeliczenie = {
  wycena: Wycena
  modele: WynikModelu[]
  wyjasnienia: Wyjasnienie[]
}

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
  kroki: string[]
  wzor?: string
  zrodlo: string
  etl: string
  panel: string
  uwagi?: string
}

