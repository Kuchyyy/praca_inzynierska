// Liczby po polsku: spacja między tysiącami, przecinek dziesiętny.

export function liczba(wartosc: number, miejsca = 0) {
  return wartosc.toLocaleString("pl-PL", {
    minimumFractionDigits: miejsca,
    maximumFractionDigits: miejsca,
  })
}

export function zlotych(wartosc: number) {
  return `${liczba(Math.round(wartosc / 100) * 100)} zł`
}

export function zaM2(wartosc: number) {
  return `${liczba(wartosc, 2)} zł/m²`
}

// Wartość cechy z jednostką. Długie odległości pokazujemy w kilometrach.
export function wartoscCechy(wartosc: number, jednostka: string) {
  if (jednostka === "m" && wartosc >= 1000) {
    return `${liczba(wartosc / 1000, 1)} km`
  }
  const miejsca = Number.isInteger(wartosc) ? 0 : 2
  const tekst = liczba(wartosc, miejsca)
  return jednostka ? `${tekst} ${jednostka}` : tekst
}

export function zeZnakiem(wartosc: number) {
  const znak = wartosc > 0 ? "+" : "−"
  return `${znak}${liczba(Math.abs(wartosc), 2)}`
}

// Czas kroku z backendu w sekundach. Krótkie kroki w milisekundach.
export function czas(sekundy: number) {
  if (sekundy < 1) {
    return `${liczba(Math.max(sekundy * 1000, 1))} ms`
  }
  return `${liczba(sekundy, 1)} s`
}

// Data z backendu (RRRR-MM-DD) po polsku: DD.MM.RRRR.
export function data(iso: string) {
  const [rok, miesiac, dzien] = iso.split("-")
  return rok && miesiac && dzien ? `${dzien}.${miesiac}.${rok}` : iso
}

// Duże kwoty skrótem, np. „6,1 mln zł”.
export function kwota(wartosc: number) {
  if (wartosc >= 1_000_000) {
    return `${liczba(wartosc / 1_000_000, 2)} mln zł`
  }
  return zlotych(wartosc)
}
