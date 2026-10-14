// Usługa lokalizacji działek katastralnych GUGiK. Działa z przeglądarki (CORS),
// więc do wskazania działki nie potrzeba naszego backendu.

import type { Granica, Punkt } from "@/typy"
import { obwod, pole, zWkt } from "./geometria"

const ADRES = "https://uldk.gugik.gov.pl/"
const POLA = "id,geom_wkt,voivodeship,county,commune,region,parcel"

export type DzialkaUldk = {
  identyfikator: string
  numer: string
  obreb: string
  gmina: string
  powiat: string
  wojewodztwo: string
  granica: Granica
  pole: number
  obwod: number
}

export type ObrebUldk = {
  teryt: string
  obreb: string
  gmina: string
  powiat: string
  wojewodztwo: string
}

async function zapytaj(parametry: Record<string, string>) {
  const odpowiedz = await fetch(ADRES + "?" + new URLSearchParams(parametry))
  if (!odpowiedz.ok) {
    throw new Error(`ULDK odpowiedział kodem ${odpowiedz.status}`)
  }
  const wiersze = (await odpowiedz.text()).trim().split("\n").map((w) => w.trim())

  // Pierwszy wiersz to status. „-1 brak wyników” oznacza, że nic nie znaleziono.
  if (wiersze[0].startsWith("-1")) {
    return []
  }
  return wiersze.slice(1).filter((w) => w.includes("|") || w.length > 0)
}

function zWiersza(wiersz: string) {
  const [identyfikator, wkt, wojewodztwo, powiat, gmina, obreb, numer] = wiersz.split("|")
  return { identyfikator, numer, obreb, gmina, powiat, wojewodztwo, granica: zWkt(wkt) }
}

// Pole i obwód liczymy z granicy w EPSG:2180, tak samo jak w ETL.
async function dodajPomiary(dzialka: ReturnType<typeof zWiersza>): Promise<DzialkaUldk> {
  const wiersze = await zapytaj({
    request: "GetParcelById",
    id: dzialka.identyfikator,
    result: "geom_wkt",
    srid: "2180",
  })
  const granica2180 = zWkt(wiersze[0])
  return { ...dzialka, pole: pole(granica2180), obwod: obwod(granica2180) }
}

export async function dzialkaWPunkcie(punkt: Punkt) {
  const wiersze = await zapytaj({
    request: "GetParcelByXY",
    xy: `${punkt[0]},${punkt[1]},4326`,
    result: POLA,
    srid: "4326",
  })
  if (wiersze.length === 0) {
    return null
  }
  return dodajPomiary(zWiersza(wiersze[0]))
}

// Dla narysowanej granicy bierzemy obręb, gminę i powiat z punktu w jej środku.
export async function obrebWPunkcie(punkt: Punkt): Promise<ObrebUldk | null> {
  const wiersze = await zapytaj({
    request: "GetRegionByXY",
    xy: `${punkt[0]},${punkt[1]},4326`,
    result: "teryt,region,commune,county,voivodeship",
  })
  if (wiersze.length === 0) {
    return null
  }
  const [teryt, obreb, gmina, powiat, wojewodztwo] = wiersze[0].split("|")
  return { teryt, obreb, gmina, powiat, wojewodztwo }
}
