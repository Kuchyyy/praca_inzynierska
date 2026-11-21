import { useEffect, useRef, useState } from "react"
import {
  LngLatBounds,
  Map as MapaMaplibre,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type GeoJSONSource,
  type MapMouseEvent,
} from "maplibre-gl"
import adresWorkera from "maplibre-gl/dist/maplibre-gl-worker.mjs?url"
import type { Feature, FeatureCollection } from "geojson"
import {
  TerraDraw,
  TerraDrawPolygonMode,
  TerraDrawSelectMode,
  ValidateNotSelfIntersecting,
} from "terra-draw"
import { TerraDrawMapLibreGLAdapter } from "terra-draw-maplibre-gl-adapter"
import { CheckIcon, PencilIcon, RotateCcwIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"
import { kolorCss } from "@/lib/kolory"
import { KAFLE_GRANIC, KAFLE_NUMEROW, ZOOM_GRANIC, ZOOM_NUMEROW } from "@/lib/ewidencja"
import { okrag, ramka } from "@/lib/geometria"
import { data, liczba, zaM2 } from "@/lib/format"
import { RODZAJE_GRUNTU, nazwaOpcji } from "@/dane/slowniki"
import type { Granica, Punkt, Transakcja } from "@/typy"

const START_MAPY: Punkt = [20.0886, 50.0187]

const STYL_MAPY = "https://tiles.openfreemap.org/styles/positron"

const PUSTE: FeatureCollection = { type: "FeatureCollection", features: [] }

type Rysowanie = "brak" | "rysuje" | "edytuje"

function granicaKsztaltu(narzedzie: TerraDraw, id: string | number): Granica | null {
  const obiekt = narzedzie.getSnapshotFeature(id)
  if (!obiekt || obiekt.geometry.type !== "Polygon") {
    return null
  }
  return [obiekt.geometry.coordinates as Punkt[][]]
}

setWorkerUrl(adresWorkera)

type Wybor = {
  szukam: boolean
  komunikat: string
  onKlik: (punkt: Punkt) => void
  onNarysowano: (granica: Granica) => void
}

type Props = {
  granica: Granica | null
  srodek: Punkt | null
  transakcje?: Transakcja[]
  wybor?: Wybor
  className?: string
}

function maWebGl2() {
  try {
    return document.createElement("canvas").getContext("webgl2") !== null
  } catch {
    return false
  }
}

export function Mapa({ granica, srodek, transakcje, wybor, className }: Props) {
  const kontener = useRef<HTMLDivElement>(null)
  const mapa = useRef<MapaMaplibre | null>(null)
  const rysowanie = useRef<TerraDraw | null>(null)
  const wyborRef = useRef(wybor)
  const rysowanieRef = useRef<Rysowanie>("brak")
  const idKsztaltu = useRef<string | number | null>(null)
  const zamykaPrzycisk = useRef(false)
  const [uwaga, setUwaga] = useState("")
  const [gotowa, setGotowa] = useState(false)
  const [rysowanieStan, setRysowanieStan] = useState<Rysowanie>("brak")
  const [zoom, setZoom] = useState(14)
  const [bezMapy] = useState(() => !maWebGl2())

  useEffect(() => {
    wyborRef.current = wybor
  }, [wybor])

  useEffect(() => {
    if (!kontener.current || bezMapy) {
      return
    }

    const nowa = new MapaMaplibre({
      container: kontener.current,
      style: STYL_MAPY,
      center: START_MAPY,
      zoom: 14,
    })
    nowa.addControl(new NavigationControl({ showCompass: false }), "bottom-right")

    nowa.on("load", () => {
      nowa.addSource("ewidencja-granice", {
        type: "raster",
        tiles: [KAFLE_GRANIC],
        tileSize: 512,
        minzoom: ZOOM_GRANIC,
        attribution: "Ewidencja: GUGiK",
      })
      nowa.addSource("ewidencja-numery", {
        type: "raster",
        tiles: [KAFLE_NUMEROW],
        tileSize: 512,
        minzoom: ZOOM_NUMEROW,
      })
      nowa.addSource("okregi", { type: "geojson", data: PUSTE })
      nowa.addSource("transakcje", { type: "geojson", data: PUSTE })
      nowa.addSource("dzialka", { type: "geojson", data: PUSTE })
      nowa.addSource("srodek", { type: "geojson", data: PUSTE })

      nowa.addLayer({ id: "ewidencja-granice", type: "raster", source: "ewidencja-granice", minzoom: ZOOM_GRANIC })
      nowa.addLayer({ id: "ewidencja-numery", type: "raster", source: "ewidencja-numery", minzoom: ZOOM_NUMEROW })
      nowa.addLayer({
        id: "okregi",
        type: "line",
        source: "okregi",
        paint: { "line-color": kolorCss("rynek"), "line-width": 1.5, "line-dasharray": [3, 3] },
      })
      nowa.addLayer({
        id: "transakcje",
        type: "circle",
        source: "transakcje",
        paint: {
          "circle-radius": 5,
          "circle-color": kolorCss("rynek"),
          "circle-stroke-color": "#FFFFFF",
          "circle-stroke-width": 1.5,
        },
      })
      nowa.addLayer({
        id: "dzialka-obwodka",
        type: "line",
        source: "dzialka",
        paint: { "line-color": "#FFFFFF", "line-width": 7 },
      })
      nowa.addLayer({
        id: "dzialka",
        type: "line",
        source: "dzialka",
        paint: { "line-color": kolorCss("akcja"), "line-width": 3.5 },
      })
      nowa.addLayer({
        id: "srodek",
        type: "circle",
        source: "srodek",
        maxzoom: 14,
        paint: {
          "circle-radius": 7,
          "circle-color": kolorCss("akcja"),
          "circle-stroke-color": "#FFFFFF",
          "circle-stroke-width": 2,
        },
      })

      if (wyborRef.current) {
        const akcja = kolorCss("akcja") as `#${string}`
        const narzedzie = new TerraDraw({
          adapter: new TerraDrawMapLibreGLAdapter({ map: nowa }),
          modes: [
            new TerraDrawSelectMode({
              allowManualDeselection: false,
              flags: {
                polygon: {
                  feature: {
                    draggable: true,
                    selfIntersectable: false,
                    coordinates: { draggable: true, midpoints: true, deletable: true },
                  },
                },
              },
              styles: {
                selectedPolygonColor: akcja,
                selectedPolygonFillOpacity: 0,
                selectedPolygonOutlineColor: akcja,
                selectedPolygonOutlineWidth: 3,
                selectionPointColor: akcja,
                selectionPointWidth: 6,
                selectionPointOutlineColor: "#FFFFFF",
                selectionPointOutlineWidth: 2,
                midPointColor: "#FFFFFF",
                midPointWidth: 4,
                midPointOutlineColor: akcja,
                midPointOutlineWidth: 2,
              },
            }),
            new TerraDrawPolygonMode({
              validation: (obiekt) => ValidateNotSelfIntersecting(obiekt),
              styles: {
                fillColor: akcja,
                fillOpacity: 0,
                outlineColor: akcja,
                outlineWidth: 2,
                closingPointColor: akcja,
                closingPointWidth: 6,
                closingPointOutlineColor: "#FFFFFF",
                closingPointOutlineWidth: 2,
              },
            }),
          ],
        })
        narzedzie.start()
        narzedzie.on("finish", (id, kontekst) => {
          if (kontekst.mode !== "polygon") {
            return
          }
          idKsztaltu.current = id
          if (zamykaPrzycisk.current) {
            return
          }
          narzedzie.setMode("select")
          narzedzie.selectFeature(id)
          setRysowanieStan("edytuje")
        })
        rysowanie.current = narzedzie
      }
      setGotowa(true)
    })

    const dymek = new Popup({ closeButton: false, closeOnClick: false, offset: 8 })
    nowa.on("mouseenter", "transakcje", (zdarzenie) => {
      const obiekt = zdarzenie.features?.[0]
      if (!obiekt || obiekt.geometry.type !== "Point") {
        return
      }
      const p = obiekt.properties
      nowa.getCanvas().style.cursor = "pointer"
      dymek
        .setLngLat(obiekt.geometry.coordinates as Punkt)
        .setHTML(
          `<strong>${zaM2(p.cena)}</strong><br>${data(p.data)} · ${liczba(p.powierzchnia)} m²<br>${nazwaOpcji(RODZAJE_GRUNTU, p.rodzaj)}`
        )
        .addTo(nowa)
    })
    nowa.on("mouseleave", "transakcje", () => {
      nowa.getCanvas().style.cursor = ""
      dymek.remove()
    })

    nowa.on("zoomend", () => setZoom(nowa.getZoom()))

    nowa.on("click", (zdarzenie: MapMouseEvent) => {
      if (rysowanieRef.current !== "brak") {
        setUwaga("")
        return
      }
      wyborRef.current?.onKlik([zdarzenie.lngLat.lng, zdarzenie.lngLat.lat])
    })

    mapa.current = nowa
    return () => {
      rysowanie.current?.stop()
      rysowanie.current = null
      nowa.remove()
      mapa.current = null
    }
  }, [bezMapy])

  useEffect(() => {
    rysowanieRef.current = rysowanieStan
  }, [rysowanieStan])

  function zacznijRysowanie() {
    const narzedzie = rysowanie.current
    if (!narzedzie) {
      return
    }
    narzedzie.setMode("static")
    narzedzie.clear()
    narzedzie.setMode("polygon")
    idKsztaltu.current = null
    rysowanieRef.current = "rysuje"
    setUwaga("")
    setRysowanieStan("rysuje")
  }

  function wylaczRysowanie() {
    const narzedzie = rysowanie.current
    if (narzedzie) {
      narzedzie.setMode("static")
      narzedzie.clear()
    }
    idKsztaltu.current = null
    setUwaga("")
    setRysowanieStan("brak")
  }

  function zakonczRysowanie() {
    const narzedzie = rysowanie.current
    const m = mapa.current
    if (!narzedzie || !m) {
      return
    }

    if (rysowanieStan === "rysuje") {
      zamykaPrzycisk.current = true
      m.getCanvas().dispatchEvent(new KeyboardEvent("keyup", { key: "Enter" }))
      zamykaPrzycisk.current = false
      if (idKsztaltu.current === null) {
        setUwaga("Postaw co najmniej trzy narożniki, żeby powstało pole.")
        return
      }
    }

    if (idKsztaltu.current === null) {
      return
    }
    const granica = granicaKsztaltu(narzedzie, idKsztaltu.current)
    if (granica) {
      wyborRef.current?.onNarysowano(granica)
    }
    wylaczRysowanie()
  }

  useEffect(() => {
    const m = mapa.current
    if (!m || !gotowa) {
      return
    }

    const zrodloDzialki = m.getSource("dzialka") as GeoJSONSource
    const zrodloTransakcji = m.getSource("transakcje") as GeoJSONSource
    const zrodloOkregow = m.getSource("okregi") as GeoJSONSource
    const zrodloSrodka = m.getSource("srodek") as GeoJSONSource

    if (!granica || !srodek) {
      zrodloDzialki.setData(PUSTE)
      zrodloSrodka.setData(PUSTE)
      zrodloTransakcji.setData(PUSTE)
      zrodloOkregow.setData(PUSTE)
      return
    }

    zrodloDzialki.setData({
      type: "Feature",
      properties: {},
      geometry: { type: "MultiPolygon", coordinates: granica },
    })
    zrodloSrodka.setData({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: srodek } })

    if (!transakcje) {
      zrodloTransakcji.setData(PUSTE)
      zrodloOkregow.setData(PUSTE)
      m.fitBounds(ramka(granica), { padding: 120, maxZoom: 18, duration: 600 })
      return
    }

    const punkty: Feature[] = []
    for (const transakcja of transakcje) {
      punkty.push({
        type: "Feature",
        properties: {
          cena: transakcja.cenaM2,
          data: transakcja.data,
          powierzchnia: transakcja.powierzchnia,
          rodzaj: transakcja.rodzaj ?? "",
        },
        geometry: { type: "Point", coordinates: transakcja.punkt },
      })
    }
    zrodloTransakcji.setData({ type: "FeatureCollection", features: punkty })

    const okrag5km = okrag(srodek, 5000)
    zrodloOkregow.setData({
      type: "FeatureCollection",
      features: [
        { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: okrag(srodek, 2000) } },
        { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: okrag5km } },
      ],
    })

    const granice = new LngLatBounds(okrag5km[0], okrag5km[0])
    for (const punkt of okrag5km) {
      granice.extend(punkt)
    }
    m.fitBounds(granice, { padding: 24, duration: 600 })
  }, [gotowa, granica, srodek, transakcje])

  return (
    <div className={cn("relative overflow-hidden rounded-sm border", className)}>
      <div ref={kontener} style={{ position: "absolute", inset: 0 }} />

      {wybor && (
        <div className="absolute inset-x-0 top-0 flex items-center gap-2 border-b bg-card p-2">

          <Button variant="outline" onClick={zacznijRysowanie} disabled={bezMapy}>
            {rysowanieStan === "brak" ? <PencilIcon data-icon="inline-start" /> : <RotateCcwIcon data-icon="inline-start" />}
            {rysowanieStan === "brak" ? "Narysuj granicę" : "Rysuj od nowa"}
          </Button>
          {rysowanieStan !== "brak" && (
            <>
              <Button onClick={zakonczRysowanie}>
                <CheckIcon data-icon="inline-start" />
                Zakończ wybieranie pola
              </Button>
              <Button variant="ghost" onClick={wylaczRysowanie}>
                <XIcon data-icon="inline-start" />
                Anuluj
              </Button>
            </>
          )}
        </div>
      )}

      {wybor && rysowanieStan !== "brak" && (
        <div className="absolute top-15 left-2 w-96 rounded-sm border border-akcja bg-card p-3 text-xs">
          {rysowanieStan === "rysuje"
            ? "Klikaj kolejne narożniki działki. Kliknij pierwszy punkt, aby zamknąć kształt i go poprawić, albo od razu kliknij „Zakończ wybieranie pola”."
            : "Przeciągaj narożniki, aby poprawić kształt. Białe punkty na bokach dodają nowy narożnik. Gdy kształt jest gotowy, kliknij „Zakończ wybieranie pola”."}
          {uwaga && <p className="mt-1.5 font-medium text-ostrzezenie">{uwaga}</p>}
        </div>
      )}

      {wybor && (wybor.szukam || wybor.komunikat) && (
        <div className="absolute bottom-8 left-3 flex max-w-96 items-center gap-2 rounded-sm border bg-card px-3 py-2 text-xs">
          {wybor.szukam ? (
            <>
              <Spinner />
              Szukam działki w ewidencji (ULDK)…
            </>
          ) : (
            <span className="text-ostrzezenie">{wybor.komunikat}</span>
          )}
        </div>
      )}

      {bezMapy && (
        <div
          className={cn(
            "absolute inset-0 flex items-center justify-center bg-muted p-6 text-center text-sm text-muted-foreground",
            wybor && "top-13"
          )}
        >
          Ta przeglądarka nie obsługuje WebGL2, więc mapy nie da się wyświetlić.
        </div>
      )}

      {wybor && !bezMapy && rysowanieStan === "brak" && zoom < ZOOM_GRANIC && (
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 rounded-sm bg-primary px-3 py-1.5 text-xs text-primary-foreground">
          Przybliż mapę, aby zobaczyć granice działek
        </div>
      )}
    </div>
  )
}
