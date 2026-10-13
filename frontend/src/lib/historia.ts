import type { DaneDzialki, WynikWyceny } from "@/typy"

// Ostatnie wyceny zapisane w tej przeglądarce. To tylko wygoda: bez dostępu do pamięci
// (tryb prywatny, wyczyszczone dane) lista jest pusta, a panel działa dalej.
const KLUCZ = "wycena-dzialek:historia"
const LIMIT = 8

export type WpisHistorii = {
  czas: string
  dzialka: DaneDzialki
  cenaM2: number
  wartosc: number
  model: string
}

export function wczytajHistorie(): WpisHistorii[] {
  try {
    const tekst = localStorage.getItem(KLUCZ)
    return tekst ? JSON.parse(tekst) : []
  } catch {
    return []
  }
}

function zapisz(lista: WpisHistorii[]) {
  try {
    localStorage.setItem(KLUCZ, JSON.stringify(lista))
  } catch {
    // Brak miejsca albo zablokowana pamięć: historia po prostu się nie zapisze.
  }
}

// Nowa wycena trafia na początek. Ta sama działka nie powtarza się na liście.
export function dopiszDoHistorii(dzialka: DaneDzialki, wynik: WynikWyceny) {
  const powierzchnia = Number(dzialka.powierzchnia.replace(",", "."))
  const wpis: WpisHistorii = {
    czas: new Date().toISOString(),
    dzialka,
    cenaM2: wynik.wycena.cenaM2,
    wartosc: wynik.wycena.cenaM2 * powierzchnia,
    model: wynik.wycena.model,
  }
  const pozostale = wczytajHistorie().filter((w) => w.dzialka.identyfikator !== dzialka.identyfikator)
  const lista = [wpis, ...pozostale].slice(0, LIMIT)
  zapisz(lista)
  return lista
}

export function wyczyscHistorie() {
  zapisz([])
  return []
}
