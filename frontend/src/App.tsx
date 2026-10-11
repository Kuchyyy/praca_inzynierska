import { useEffect, useRef, useState } from "react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { OPISY_CECH } from "@/dane/opisyCech"
import { pobierzOpisModelu, podpowiedzObrebu, przeliczCechy, wycenDzialke } from "@/lib/api"
import { zRysunku, zUldk } from "@/lib/dzialka"
import { dzialkaPoNumerze, dzialkaWPunkcie, obrebWPunkcie } from "@/lib/uldk"
import { srodek } from "@/lib/geometria"
import { cn } from "@/lib/utils"
import { CechyDzialki } from "@/komponenty/CechyDzialki"
import { FormularzDanych } from "@/komponenty/FormularzDanych"
import { HistoriaCen } from "@/komponenty/HistoriaCen"
import { IkonaModulu } from "@/komponenty/IkonaModulu"
import { Mapa } from "@/komponenty/Mapa"
import { Naglowek } from "@/komponenty/Naglowek"
import { OpisCech } from "@/komponenty/OpisCech"
import { PorownanieModeli } from "@/komponenty/PorownanieModeli"
import { Proces } from "@/komponenty/Proces"
import { SlownikCech } from "@/komponenty/SlownikCech"
import { WplywCech } from "@/komponenty/WplywCech"
import { Wynik } from "@/komponenty/Wynik"
import type {
  Cechy,
  DaneDzialki,
  Etap,
  Granica,
  OpisModelu,
  Podpowiedz,
  Postep,
  Przeliczenie,
  Punkt,
  Widok,
  WynikWyceny,
} from "@/typy"

const POCZATEK: Postep = { krok: 0, podkrok: 0, kroki: [] }

export function App() {
  const [etap, setEtap] = useState<Etap>("dane")
  // Opis cech to osobny widok tej samej strony. Wycena zostaje w pamięci pod spodem.
  const [widok, setWidok] = useState<Widok>("wycena")
  const [celCechy, setCelCechy] = useState<string | null>(null)
  const [opisModelu, setOpisModelu] = useState<OpisModelu | null>(null)
  const [dzialka, setDzialka] = useState<DaneDzialki | null>(null)
  const [podpowiedz, setPodpowiedz] = useState<Podpowiedz | null>(null)
  const [postep, setPostep] = useState<Postep>(POCZATEK)
  const [blad, setBlad] = useState("")
  const [wynik, setWynik] = useState<WynikWyceny | null>(null)
  // Wynik trybu „co jeśli”. Pusty, dopóki nikt nie zmienił cech.
  const [przeliczenie, setPrzeliczenie] = useState<Przeliczenie | null>(null)
  const [rozwiniety, setRozwiniety] = useState(false)
  const [wybranaCecha, setWybranaCecha] = useState(OPISY_CECH[0].kod)
  const [szukam, setSzukam] = useState(false)
  const [komunikat, setKomunikat] = useState("")
  // Liczą zapytania, żeby spóźniona odpowiedź nie nadpisała nowszej.
  const numerZapytania = useRef(0)
  const numerWyceny = useRef(0)
  const pozycjaWyceny = useRef(0)

  // Metryki i statystyki modeli do opisu cech. Pobierane raz, przy starcie panelu.
  useEffect(() => {
    pobierzOpisModelu().then(setOpisModelu)
  }, [])

  // Podpowiedź przeznaczenia z transakcji w obrębie wybranej działki.
  const obreb = dzialka?.terytObrebu ?? ""
  useEffect(() => {
    if (!obreb) {
      return
    }
    let aktualne = true
    podpowiedzObrebu(obreb).then((wynikPodpowiedzi) => {
      if (aktualne) {
        setPodpowiedz(wynikPodpowiedzi)
      }
    })
    return () => {
      aktualne = false
      setPodpowiedz(null)
    }
  }, [obreb])

  // Wspólna obsługa zapytań do ULDK: stan ładowania, brak wyniku i błąd sieci.
  async function zapytajUldk(zapytanie: () => Promise<DaneDzialki | null>, brak: string) {
    const numer = ++numerZapytania.current
    setSzukam(true)
    setKomunikat("")
    try {
      const znaleziona = await zapytanie()
      if (numer !== numerZapytania.current) {
        return
      }
      if (znaleziona) {
        setDzialka(znaleziona)
      } else {
        setKomunikat(brak)
      }
    } catch {
      if (numer === numerZapytania.current) {
        setKomunikat("Nie udało się połączyć z ULDK. Spróbuj ponownie albo narysuj granicę.")
      }
    } finally {
      if (numer === numerZapytania.current) {
        setSzukam(false)
      }
    }
  }

  function kliknietoMape(punkt: Punkt) {
    zapytajUldk(
      async () => {
        const znaleziona = await dzialkaWPunkcie(punkt)
        return znaleziona ? zUldk(znaleziona) : null
      },
      "W tym miejscu ewidencja nie ma działki. Przybliż mapę albo narysuj granicę."
    )
  }

  function wyszukano(tekst: string) {
    zapytajUldk(
      async () => {
        const znaleziona = await dzialkaPoNumerze(tekst)
        return znaleziona ? zUldk(znaleziona) : null
      },
      `Nie znaleziono działki „${tekst.trim()}”. Wpisz nazwę obrębu i numer, np. Kokotów 43/1.`
    )
  }

  function narysowano(granica: Granica) {
    zapytajUldk(
      async () => {
        const obrebRysunku = await obrebWPunkcie(srodek(granica))
        return obrebRysunku ? zRysunku(granica, obrebRysunku) : null
      },
      "Narysowana granica leży poza obrębami ewidencyjnymi."
    )
  }

  // Backend liczy cechy i modele, a po każdym kroku przysyła postęp.
  async function wycen() {
    if (!dzialka) {
      return
    }
    const numer = ++numerWyceny.current
    setPostep(POCZATEK)
    setBlad("")
    setWynik(null)
    setPrzeliczenie(null)
    setRozwiniety(false)
    setEtap("liczenie")

    try {
      const gotowy = await wycenDzialke(dzialka, (zdarzenie) => {
        if (numer !== numerWyceny.current) {
          return
        }
        if ("podkrok" in zdarzenie) {
          setPostep((p) => ({ ...p, krok: zdarzenie.krok - 1, podkrok: zdarzenie.podkrok + 1 }))
        } else {
          const gotowyKrok = { numer: zdarzenie.krok, wynik: zdarzenie.wynik, czas: zdarzenie.czas }
          setPostep((p) => ({ krok: zdarzenie.krok, podkrok: 0, kroki: [...p.kroki, gotowyKrok] }))
        }
      })
      if (numer === numerWyceny.current) {
        setWynik(gotowy)
        setEtap("wynik")
        // Gdy serwer nie działał przy starcie panelu, opis modeli pobieramy teraz.
        if (!opisModelu) {
          pobierzOpisModelu().then(setOpisModelu)
        }
      }
    } catch (e) {
      if (numer === numerWyceny.current) {
        setBlad(e instanceof Error ? e.message : String(e))
      }
    }
  }

  function anuluj() {
    numerWyceny.current++
    setEtap("dane")
  }

  // Tryb „co jeśli”: te same modele na zmienionych cechach. Bez zmian wracamy do wyniku.
  async function przelicz(cechy: Cechy | null) {
    if (!cechy) {
      setPrzeliczenie(null)
      return
    }
    setPrzeliczenie(await przeliczCechy(cechy))
  }

  // Otwiera opis cech, a gdy podano kod, przewija do tej cechy.
  function otworzCechy(kod: string | null) {
    pozycjaWyceny.current = window.scrollY
    setCelCechy(kod)
    setWidok("cechy")
  }

  // Powrót do wyceny w to samo miejsce strony.
  function wrocDoWyceny() {
    setWidok("wycena")
    requestAnimationFrame(() => window.scrollTo({ top: pozycjaWyceny.current }))
  }

  const biezaca = przeliczenie ?? wynik

  return (
    <div className="flex min-h-svh flex-col">
      <Naglowek
        etap={etap}
        widok={widok}
        dzialka={dzialka}
        onAnuluj={anuluj}
        onPonownie={() => setEtap("dane")}
        onCechy={() => otworzCechy(null)}
        onWroc={wrocDoWyceny}
      />

      <main className="flex flex-col gap-4 p-5">
        {widok === "cechy" && (
          <OpisCech model={opisModelu} wynik={wynik} cel={celCechy} onWroc={wrocDoWyceny} />
        )}

        {/* Ukrywamy zamiast usuwać, żeby powrót z opisu cech nie gubił zmian w tabeli cech. */}
        <div className={cn("flex flex-col gap-4", widok === "cechy" && "hidden")}>
        {etap === "dane" && (
          <div className="flex items-start gap-4">
            {/* Mapa przyklejona pod nagłówkiem: zostaje na ekranie przy przewijaniu formularza. */}
            <Card className="sticky top-19 h-[calc(100svh-6rem)] min-h-120 flex-1">
              <CardHeader>
                <CardTitle>1. Wskaż działkę</CardTitle>
                <CardDescription>
                  Kliknij działkę na mapie, wyszukaj ją po numerze albo narysuj jej granicę
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col">
                <Mapa
                  granica={dzialka?.granica ?? null}
                  srodek={dzialka?.srodek ?? null}
                  wybor={{
                    szukam,
                    komunikat,
                    onKlik: kliknietoMape,
                    onSzukaj: wyszukano,
                    onNarysowano: narysowano,
                  }}
                  className="flex-1"
                />
              </CardContent>
            </Card>
            <FormularzDanych dzialka={dzialka} podpowiedz={podpowiedz} onZmien={setDzialka} onWycen={wycen} />
          </div>
        )}

        {etap !== "dane" && dzialka && (
          <Proces
            dzialka={dzialka}
            postep={postep}
            blad={blad}
            czasRazem={wynik?.czas ?? null}
            zakonczony={etap === "wynik"}
            rozwiniety={rozwiniety}
            onPrzelacz={() => setRozwiniety(!rozwiniety)}
            onWroc={() => setEtap("dane")}
          />
        )}

        {etap === "wynik" && dzialka && wynik && biezaca && (
          <>
            <div className="grid grid-cols-[1fr_440px] gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2.5">
                    <IkonaModulu kolor="sukces" />
                    Mapa
                  </CardTitle>
                  <CardDescription className="pl-8.5">Działka i transakcje z okolicy</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-3">
                  <Mapa
                    granica={dzialka.granica}
                    srodek={dzialka.srodek}
                    transakcje={wynik.transakcje}
                    className="min-h-117.5 flex-1"
                  />
                  <div className="flex gap-2">
                    <Badge variant="akcja">Wyceniana działka</Badge>
                    <Badge variant="rynek">Transakcje RCN (24 mies.) · {wynik.transakcje.length}</Badge>
                    <Badge variant="outline">Promień 2 i 5 km</Badge>
                  </div>
                </CardContent>
              </Card>
              <div className="flex flex-col gap-4">
                <Wynik
                  dzialka={dzialka}
                  wycena={biezaca.wycena}
                  bazowa={wynik.wycena}
                  uwagi={wynik.wycena.uwagi ?? []}
                />
                <PorownanieModeli modele={biezaca.modele} najlepszy={wynik.wycena.model} testOd={opisModelu?.test.od ?? ""} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <WplywCech
                wyjasnienia={biezaca.wyjasnienia}
                cechy={wynik.cechy}
                waznosc={opisModelu?.waznosc ?? {}}
                najlepszy={wynik.wycena.model}
              />
              <CechyDzialki
                cechy={wynik.cechy}
                naTle={wynik.naTle}
                cenaM2={wynik.wycena.cenaM2}
                przeliczona={przeliczenie?.wycena.cenaM2 ?? null}
                onPrzelicz={przelicz}
                onWybierzCeche={otworzCechy}
              />
            </div>

            <div className="grid grid-cols-[1fr_440px] gap-4">
              <HistoriaCen
                gmina={dzialka.gmina}
                historia={wynik.historia}
                trend={wynik.cechy.trend_cen_gmina_12m as number | null}
                cenaM2={biezaca.wycena.cenaM2}
              />
              <SlownikCech
                wybrana={wybranaCecha}
                onWybierz={setWybranaCecha}
                model={opisModelu}
                onPelnyOpis={otworzCechy}
              />
            </div>
          </>
        )}
        </div>
      </main>
    </div>
  )
}

export default App
