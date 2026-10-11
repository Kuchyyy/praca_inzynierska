import type { Granica, Punkt } from "@/typy"

// Pole pierścienia wzorem Gaussa. Wynik w jednostkach współrzędnych do kwadratu.
function polePierscienia(punkty: Punkt[]) {
  let suma = 0
  for (let i = 0; i < punkty.length - 1; i++) {
    suma += punkty[i][0] * punkty[i + 1][1] - punkty[i + 1][0] * punkty[i][1]
  }
  return Math.abs(suma) / 2
}

function dlugoscPierscienia(punkty: Punkt[]) {
  let suma = 0
  for (let i = 0; i < punkty.length - 1; i++) {
    suma += Math.hypot(punkty[i + 1][0] - punkty[i][0], punkty[i + 1][1] - punkty[i][1])
  }
  return suma
}

// Tak jak shapely w ETL: pole zewnętrznych pierścieni minus dziury.
export function pole(granica: Granica) {
  let wynik = 0
  for (const wielokat of granica) {
    wynik += polePierscienia(wielokat[0])
    for (const dziura of wielokat.slice(1)) {
      wynik -= polePierscienia(dziura)
    }
  }
  return wynik
}

// Tak jak shapely w ETL: obwód obejmuje też brzegi dziur.
export function obwod(granica: Granica) {
  let wynik = 0
  for (const wielokat of granica) {
    for (const pierscien of wielokat) {
      wynik += dlugoscPierscienia(pierscien)
    }
  }
  return wynik
}

export function zwartosc(poleM2: number, obwodM: number) {
  return obwodM > 0 ? (4 * Math.PI * poleM2) / obwodM ** 2 : 0
}

// Środek ciężkości największego wielokąta. Wystarcza do mapy i okręgów sąsiedztwa.
export function srodek(granica: Granica): Punkt {
  let najwiekszy = granica[0][0]
  for (const wielokat of granica) {
    if (polePierscienia(wielokat[0]) > polePierscienia(najwiekszy)) {
      najwiekszy = wielokat[0]
    }
  }

  let x = 0
  let y = 0
  let suma = 0
  for (let i = 0; i < najwiekszy.length - 1; i++) {
    const [x1, y1] = najwiekszy[i]
    const [x2, y2] = najwiekszy[i + 1]
    const iloczyn = x1 * y2 - x2 * y1
    x += (x1 + x2) * iloczyn
    y += (y1 + y2) * iloczyn
    suma += iloczyn
  }
  if (suma === 0) {
    return najwiekszy[0]
  }
  return [x / (3 * suma), y / (3 * suma)]
}

export function ramka(granica: Granica): [Punkt, Punkt] {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const wielokat of granica) {
    for (const [x, y] of wielokat[0]) {
      minX = Math.min(minX, x)
      minY = Math.min(minY, y)
      maxX = Math.max(maxX, x)
      maxY = Math.max(maxY, y)
    }
  }
  return [
    [minX, minY],
    [maxX, maxY],
  ]
}

// WKT z ULDK, np. „SRID=2180;POLYGON((x y,x y,…),(…))” albo MULTIPOLYGON.
export function zWkt(wkt: string): Granica {
  const tekst = wkt.replace(/^SRID=\d+;/, "").trim()
  const tresc = tekst.slice(tekst.indexOf("("))

  // Wielokąty multipoligonu dzielimy po „)),((”, pierścienie wycinamy z nawiasów.
  const wielokatyTekst = tekst.startsWith("MULTIPOLYGON")
    ? tresc.slice(1, -1).split(/\)\s*\)\s*,\s*\(\s*\(/)
    : [tresc]

  const granica: Granica = []
  for (const wielokatTekst of wielokatyTekst) {
    const pierscienie: Punkt[][] = []
    // Fragmenty między nawiasami to pierścienie; same przecinki między nimi pomijamy.
    const ciagi = (wielokatTekst.match(/[^()]+/g) ?? []).filter((c) => /\d/.test(c))
    for (const ciag of ciagi) {
      const punkty: Punkt[] = []
      for (const para of ciag.split(",")) {
        const [x, y] = para.trim().split(/\s+/).map(Number)
        punkty.push([x, y])
      }
      pierscienie.push(punkty)
    }
    if (pierscienie.length > 0) {
      granica.push(pierscienie)
    }
  }
  return granica
}

// Narysowana granica jest w stopniach. Do pola i obwodu przeliczamy ją lokalnie na metry.
// Na obszarze jednej działki błąd tego przybliżenia jest pomijalny.
export function naMetry(granica: Granica, wokol: Punkt): Granica {
  const metryNaStopienY = 111320
  const metryNaStopienX = 111320 * Math.cos((wokol[1] * Math.PI) / 180)
  return granica.map((wielokat) =>
    wielokat.map((pierscien) =>
      pierscien.map(([x, y]): Punkt => [(x - wokol[0]) * metryNaStopienX, (y - wokol[1]) * metryNaStopienY])
    )
  )
}

// Okrąg o promieniu w metrach wokół punktu w stopniach. Do rysowania promieni 2 i 5 km.
export function okrag(wokol: Punkt, promien: number): Punkt[] {
  const metryNaStopienY = 111320
  const metryNaStopienX = 111320 * Math.cos((wokol[1] * Math.PI) / 180)
  const punkty: Punkt[] = []
  for (let i = 0; i <= 64; i++) {
    const kat = (i / 64) * 2 * Math.PI
    punkty.push([wokol[0] + (Math.cos(kat) * promien) / metryNaStopienX, wokol[1] + (Math.sin(kat) * promien) / metryNaStopienY])
  }
  return punkty
}
