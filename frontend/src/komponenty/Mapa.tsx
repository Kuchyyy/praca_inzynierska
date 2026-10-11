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
import { CheckIcon, PencilIcon, RotateCcwIcon, SearchIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"
import { kolorCss } from "@/lib/kolory"
import { okrag, ramka } from "@/lib/geometria"
import { liczba, zaM2 } from "@/lib/format"
import { RODZAJE_GRUNTU, nazwaOpcji } from "@/dane/slowniki"
import type { Granica, Punkt, Transakcja } from "@/typy"

// Start mapy przed wyborem działki: okolice Krakowa.
const START_MAPY: Punkt = [20.0886, 50.0187]

// Neutralny podkład bez klucza API. Atrybucja OSM pokazuje się sama.
const STYL_MAPY = "https://tiles.openfreemap.org/styles/positron"

// Granice i numery działek z Krajowej Integracji Ewidencji Gruntów (GUGiK, WMS).
const EWIDENCJA =
  "https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0" +
  "&LAYERS=dzialki,numery_dzialek&STYLES=&FORMAT=image/png&TRANSPARENT=true&CRS=EPSG:3857" +
  "&BBOX={bbox-epsg-3857}&WIDTH=512&HEIGHT=512"

// Serwer ewidencji rysuje granice dopiero od skali około 1:5000; sprawdzone, że od powiększenia 17.
const ZOOM_EWIDENCJI = 17

const PUSTE: FeatureCollection = { type: "FeatureCollection", features: [] }

// Rysowanie: najpierw stawiamy narożniki, po zamknięciu kształtu można go jeszcze poprawiać.
// Granica idzie do wyceny dopiero po kliknięciu „Zakończ wybieranie pola”.
type Rysowanie = "brak" | "rysuje" | "edytuje"

// Granica narysowanego kształtu w postaci, jakiej oczekuje reszta aplikacji.
function granicaKsztaltu(narzedzie: TerraDraw, id: string | number): Granica | null {
  const obiekt = narzedzie.getSnapshotFeature(id)
  if (!obiekt || obiekt.geometry.type !== "Polygon") {
    return null
  }
  return [obiekt.geometry.coordinates as Punkt[][]]
}

// Vite przenosi bibliotekę w inne miejsce, więc MapLibre sam nie znajdzie swojego workera.
setWorkerUrl(adresWorkera)

type Wybor = {
  szukam: boolean
  komunikat: string
  onKlik: (punkt: Punkt) => void
  onSzukaj: (tekst: string) => void
  onNarysowano: (granica: Granica) => void
}

type Props = {
  granica: Granica | null
  srodek: Punkt | null
  // Po wycenie: transakcje z okolicy, z których liczono sąsiedztwo cenowe.
  transakcje?: Transakcja[]
  // Tylko na etapie wskazywania działki.
  wybor?: Wybor
  className?: string
}

export function Mapa({ granica, srodek, transakcje, wybor, className }: Props) {
  const kontener = useRef<HTMLDivElement>(null)
  const mapa = useRef<MapaMaplibre | null>(null)
  const rysowanie = useRef<TerraDraw | null>(null)
  const wyborRef = useRef(wybor)
  const rysowanieRef = useRef<Rysowanie>("brak")
  const idKsztaltu = useRef<string | number | null>(null)
  // Ustawione, gdy kształt zamyka przycisk „Zakończ”, a nie kliknięcie w pierwszy punkt.
  const zamykaPrzycisk = useRef(false)
  const [uwaga, setUwaga] = useState("")
  const [gotowa, setGotowa] = useState(false)
  const [szukane, setSzukane] = useState("")
  const [rysowanieStan, setRysowanieStan] = useState<Rysowanie>("brak")
  const [zoom, setZoom] = useState(14)

  useEffect(() => {
    wyborRef.current = wybor
  }, [wybor])

  // Mapę tworzymy raz. Dane działki zmieniamy w osobnych efektach.
  useEffect(() => {
    if (!kontener.current) {
      return
    }

    const nowa = new MapaMaplibre({
      container: kontener.current,
      style: STYL_MAPY,
      center: START_MAPY,
      zoom: 14,
    })
    // Górę mapy zajmuje pasek narzędzi, więc przyciski powiększenia są na dole.
    nowa.addControl(new NavigationControl({ showCompass: false }), "bottom-right")

    nowa.on("load", () => {
      nowa.addSource("ewidencja", {
        type: "raster",
        tiles: [EWIDENCJA],
        tileSize: 512,
        attribution: "Ewidencja: GUGiK",
      })
      nowa.addSource("okregi", { type: "geojson", data: PUSTE })
      nowa.addSource("transakcje", { type: "geojson", data: PUSTE })
      nowa.addSource("dzialka", { type: "geojson", data: PUSTE })
      nowa.addSource("srodek", { type: "geojson", data: PUSTE })

      nowa.addLayer({ id: "ewidencja", type: "raster", source: "ewidencja", minzoom: ZOOM_EWIDENCJI })
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
      // Sam obrys bez wypełnienia, żeby pod spodem było widać mapę i granice z ewidencji.
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
      // Przy małym powiększeniu działka jest za mała, więc pokazujemy jej środek.
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

      // Narzędzie do rysowania granicy. Sam obrys, bez wypełnienia i bez przezroczystości.
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
        // Zamknięty kształt od razu przechodzi w edycję: narożniki można przesuwać.
        narzedzie.on("finish", (id, kontekst) => {
          if (kontekst.mode !== "polygon") {
            return
          }
          idKsztaltu.current = id
          // Przy zamknięciu przyciskiem resztą zajmuje się „Zakończ wybieranie pola”.
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

    // Po najechaniu na transakcję pokazujemy jej cenę, datę i powierzchnię.
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
          `<strong>${zaM2(p.cena)}</strong><br>${p.data} · ${liczba(p.powierzchnia)} m²<br>${nazwaOpcji(RODZAJE_GRUNTU, p.rodzaj)}`
        )
        .addTo(nowa)
    })
    nowa.on("mouseleave", "transakcje", () => {
      nowa.getCanvas().style.cursor = ""
      dymek.remove()
    })

    nowa.on("zoomend", () => setZoom(nowa.getZoom()))

    nowa.on("click", (zdarzenie: MapMouseEvent) => {
      // Dopóki rysowanie nie jest zakończone, kliknięcia należą do narzędzia.
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
  }, [])

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

  // Dopiero tutaj granica trafia do wyceny. Działa w trakcie stawiania narożników
  // i po zamknięciu kształtu, zawsze z tym, co jest teraz narysowane.
  function zakonczRysowanie() {
    const narzedzie = rysowanie.current
    const m = mapa.current
    if (!narzedzie || !m) {
      return
    }

    if (rysowanieStan === "rysuje") {
      // Zamykamy kształt z postawionych narożników, tak jak klawisz Enter w terra-draw.
      // Bieżąca pozycja kursora nie staje się narożnikiem.
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

  // Granica działki, a po wycenie także okolica.
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

    // Pokazujemy cały promień 5 km.
    const granice = new LngLatBounds(okrag5km[0], okrag5km[0])
    for (const punkt of okrag5km) {
      granice.extend(punkt)
    }
    m.fitBounds(granice, { padding: 24, duration: 600 })
  }, [gotowa, granica, srodek, transakcje])

  function szukaj(zdarzenie: React.FormEvent) {
    zdarzenie.preventDefault()
    if (szukane.trim()) {
      wyborRef.current?.onSzukaj(szukane)
    }
  }

  return (
    <div className={cn("relative overflow-hidden rounded-sm border", className)}>
      {/* Styl inline, bo CSS MapLibre nadpisuje klasę „absolute” na „relative”. */}
      <div ref={kontener} style={{ position: "absolute", inset: 0 }} />

      {/* Pasek narzędzi przyklejony do górnej krawędzi mapy. */}
      {wybor && (
        <div className="absolute inset-x-0 top-0 flex items-center gap-2 border-b bg-card p-2">
          <form onSubmit={szukaj} className="relative w-80">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={szukane}
              onChange={(e) => setSzukane(e.target.value)}
              placeholder="Numer działki, np. Kokotów 43/1"
              className="pl-8"
              disabled={rysowanieStan !== "brak"}
            />
          </form>

          <Button variant="outline" onClick={zacznijRysowanie}>
            {rysowanieStan === "brak" ? <PencilIcon data-icon="inline-start" /> : <RotateCcwIcon data-icon="inline-start" />}
            {rysowanieStan === "brak" ? "Narysuj granicę" : "Rysuj od nowa"}
          </Button>
          <Button onClick={zakonczRysowanie} disabled={rysowanieStan === "brak"}>
            <CheckIcon data-icon="inline-start" />
            Zakończ wybieranie pola
          </Button>
          {rysowanieStan !== "brak" && (
            <Button variant="ghost" onClick={wylaczRysowanie}>
              <XIcon data-icon="inline-start" />
              Anuluj
            </Button>
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

      {wybor && rysowanieStan === "brak" && zoom < ZOOM_EWIDENCJI && (
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 rounded-sm bg-primary px-3 py-1.5 text-xs text-primary-foreground">
          Przybliż mapę, aby zobaczyć granice działek
        </div>
      )}
    </div>
  )
}
