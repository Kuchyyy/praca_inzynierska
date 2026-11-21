import type { GrupaCechy, Kolor } from "@/typy"

export const TLO: Record<Kolor, string> = {
  akcja: "bg-akcja",
  sukces: "bg-sukces",
  spadek: "bg-spadek",
  ostrzezenie: "bg-ostrzezenie",
  rynek: "bg-rynek",
  model: "bg-model",
  wynik: "bg-wynik",
}

export const RAMKA: Record<Kolor, string> = {
  akcja: "border-akcja",
  sukces: "border-sukces",
  spadek: "border-spadek",
  ostrzezenie: "border-ostrzezenie",
  rynek: "border-rynek",
  model: "border-model",
  wynik: "border-wynik",
}

export const TEKST: Record<Kolor, string> = {
  akcja: "text-akcja",
  sukces: "text-sukces",
  spadek: "text-spadek",
  ostrzezenie: "text-ostrzezenie",
  rynek: "text-rynek",
  model: "text-model",
  wynik: "text-wynik",
}

export function kolorCss(nazwa: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(`--${nazwa}`).trim()
}

export const KOLOR_GRUPY: Record<GrupaCechy, Kolor> = {
  sasiedztwo: "rynek",
  osm: "ostrzezenie",
  dzialka: "akcja",
  przeznaczenie: "wynik",
}
