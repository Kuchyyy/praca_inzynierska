import { addProtocol } from "maplibre-gl"

import { kolorCss } from "@/lib/kolory"

const WMS =
  "https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0" +
  "&STYLES=&FORMAT=image/png&TRANSPARENT=true&CRS=EPSG:3857"

export const ZOOM_GRANIC = 15
export const ZOOM_NUMEROW = 17

export const KAFLE_GRANIC = "ewidencja://granice/{bbox-epsg-3857}"
export const KAFLE_NUMEROW = "ewidencja://numery/{bbox-epsg-3857}"

type Warstwa = { nazwa: string; rozmiar: number }

const WARSTWY: Record<string, Warstwa> = {
  granice: { nazwa: "dzialki", rozmiar: 1024 },
  numery: { nazwa: "numery_dzialek", rozmiar: 512 },
}

const POGRUBIENIE: [number, number][] = [
  [0, 0],
  [1, 0],
  [0, 1],
  [1, 1],
]

function warstwaKoloru(obraz: ImageBitmap, przesuniecia: [number, number][], kolor: string) {
  const plotno = document.createElement("canvas")
  plotno.width = obraz.width
  plotno.height = obraz.height
  const kontekst = plotno.getContext("2d")!
  for (const [dx, dy] of przesuniecia) {
    kontekst.drawImage(obraz, dx, dy)
  }
  kontekst.globalCompositeOperation = "source-in"
  kontekst.fillStyle = kolor
  kontekst.fillRect(0, 0, plotno.width, plotno.height)
  return plotno
}

function rgb(kolor: string) {
  const liczba = parseInt(kolor.replace("#", ""), 16)
  return [(liczba >> 16) & 255, (liczba >> 8) & 255, liczba & 255]
}

function przemalujNumery(obraz: ImageBitmap, tekst: string, poswiata: string) {
  const plotno = document.createElement("canvas")
  plotno.width = obraz.width
  plotno.height = obraz.height
  const kontekst = plotno.getContext("2d")!
  kontekst.drawImage(obraz, 0, 0)

  const piksele = kontekst.getImageData(0, 0, plotno.width, plotno.height)
  const dane = piksele.data
  const ciemny = rgb(tekst)
  const jasny = rgb(poswiata)
  for (let i = 0; i < dane.length; i += 4) {
    if (dane[i + 3] === 0) {
      continue
    }
    const udzialTekstu = Math.min(Math.max((255 - dane[i]) / 130, 0), 1)
    for (let kanal = 0; kanal < 3; kanal++) {
      dane[i + kanal] = jasny[kanal] + (ciemny[kanal] - jasny[kanal]) * udzialTekstu
    }
  }
  kontekst.putImageData(piksele, 0, 0)
  return plotno
}

async function kafel(rodzaj: string, bbox: string, sygnal: AbortSignal) {
  const warstwa = WARSTWY[rodzaj]
  const adres = `${WMS}&LAYERS=${warstwa.nazwa}&BBOX=${bbox}&WIDTH=${warstwa.rozmiar}&HEIGHT=${warstwa.rozmiar}`
  const odpowiedz = await fetch(adres, { signal: sygnal })
  if (!odpowiedz.ok) {
    throw new Error(`Ewidencja GUGiK: ${odpowiedz.status}`)
  }
  const obraz = await createImageBitmap(await odpowiedz.blob())

  const wynik = document.createElement("canvas")
  wynik.width = obraz.width
  wynik.height = obraz.height
  const kontekst = wynik.getContext("2d")!

  if (rodzaj === "granice") {
    kontekst.drawImage(warstwaKoloru(obraz, POGRUBIENIE, kolorCss("muted-foreground")), 0, 0)
  } else {
    kontekst.drawImage(przemalujNumery(obraz, kolorCss("foreground"), kolorCss("card")), 0, 0)
  }
  obraz.close()
  return createImageBitmap(wynik)
}

addProtocol("ewidencja", async (parametry, przerwanie) => {
  const [rodzaj, bbox] = parametry.url.replace("ewidencja://", "").split("/")
  return { data: await kafel(rodzaj, bbox, przerwanie.signal) }
})
