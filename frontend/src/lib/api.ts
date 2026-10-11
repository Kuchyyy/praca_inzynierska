// Serwer wyceny w Pythonie (backend/api.py). W trybie dev Vite przekazuje /api dalej.

import type { Cechy, DaneDzialki, OpisModelu, Podpowiedz, Przeliczenie, WynikWyceny } from "@/typy"

export type Zdarzenie =
  | { krok: number; podkrok: number }
  | { krok: number; wynik: string; czas: number }

const BRAK_SERWERA =
  "Brak połączenia z serwerem wyceny. Uruchom go w katalogu backend: python api.py"

async function wyslij(adres: string, dane: unknown) {
  let odpowiedz: Response
  try {
    odpowiedz = await fetch(adres, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dane),
    })
  } catch {
    throw new Error(BRAK_SERWERA)
  }
  if (!odpowiedz.ok) {
    throw new Error(odpowiedz.status === 502 || odpowiedz.status === 504 ? BRAK_SERWERA : `Serwer odpowiedział kodem ${odpowiedz.status}`)
  }
  return odpowiedz
}

// Backend wysyła jedną linię JSON po każdym kroku i podkroku, a na końcu cały wynik.
export async function wycenDzialke(dzialka: DaneDzialki, onZdarzenie: (zdarzenie: Zdarzenie) => void) {
  const odpowiedz = await wyslij("/api/wycena", dzialka)
  const czytnik = odpowiedz.body!.getReader()
  const dekoder = new TextDecoder()
  let bufor = ""

  for (;;) {
    const { done, value } = await czytnik.read()
    if (done) {
      break
    }
    bufor += dekoder.decode(value, { stream: true })
    const linie = bufor.split("\n")
    bufor = linie.pop() ?? ""

    for (const linia of linie) {
      if (!linia.trim()) {
        continue
      }
      const dane = JSON.parse(linia)
      if ("blad" in dane) {
        throw new Error(dane.blad)
      }
      if ("wynik" in dane && typeof dane.wynik === "object") {
        return dane.wynik as WynikWyceny
      }
      onZdarzenie(dane as Zdarzenie)
    }
  }
  throw new Error("Serwer przerwał wycenę przed końcem.")
}

export async function przeliczCechy(cechy: Cechy) {
  const odpowiedz = await wyslij("/api/przelicz", { cechy })
  return (await odpowiedz.json()) as Przeliczenie
}

// Podpowiedź nie jest konieczna do wyceny, więc błąd po prostu ją ukrywa.
export async function podpowiedzObrebu(obreb: string) {
  try {
    const odpowiedz = await fetch("/api/podpowiedz?" + new URLSearchParams({ obreb }))
    if (!odpowiedz.ok) {
      return null
    }
    return (await odpowiedz.json()) as Podpowiedz | null
  } catch {
    return null
  }
}

// Metryki, ważność cech i statystyki z treningu. Bez serwera opis cech pokaże same teksty.
export async function pobierzOpisModelu() {
  try {
    const odpowiedz = await fetch("/api/model")
    if (!odpowiedz.ok) {
      return null
    }
    return (await odpowiedz.json()) as OpisModelu
  } catch {
    return null
  }
}
