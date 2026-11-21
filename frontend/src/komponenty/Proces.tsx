import { Fragment } from "react"
import { CheckIcon, ChevronDownIcon, ChevronRightIcon, ChevronUpIcon, FastForwardIcon, WorkflowIcon } from "lucide-react"

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"
import { RAMKA, TEKST, TLO } from "@/lib/kolory"
import { useLicznik } from "@/lib/animacja"
import { KROKI } from "@/dane/kroki"
import { RODZAJE_GRUNTU, nazwaOpcji } from "@/dane/slowniki"
import { czas, data, liczba } from "@/lib/format"
import type { DaneDzialki, Granica, KrokProcesu, Kolor, Postep, Punkt, WynikKroku } from "@/typy"
import { IkonaModulu } from "./IkonaModulu"

type Props = {
  dzialka: DaneDzialki
  postep: Postep
  blad: string
  czasRazem: number | null
  zakonczony: boolean
  rozwiniety: boolean
  onPrzelacz: () => void
  onWroc: () => void
  onPomin: () => void
}

type Status = "gotowe" | "trwa" | "blad" | "czeka"

function udzialKroku(indeks: number, postep: Postep, zakonczony: boolean) {
  if (zakonczony || indeks < postep.krok) {
    return 1
  }
  if (indeks > postep.krok) {
    return 0
  }
  return Math.min(postep.podkrok / KROKI[indeks].podkroki.length, 0.95)
}

export function Proces(props: Props) {
  const { dzialka, postep, blad, czasRazem, zakonczony, rozwiniety, onPrzelacz, onWroc, onPomin } = props
  const biezacy = KROKI[Math.min(postep.krok, KROKI.length - 1)]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2.5">
          <IkonaModulu kolor="akcja" ikona={WorkflowIcon} />
          Proces wyceny
        </CardTitle>
        <CardDescription className="pl-8.5">
          {zakonczony && czasRazem !== null
            ? `Wszystkie kroki zakończone · obliczenia ${czas(czasRazem)}`
            : `Liczę wycenę działki ${dzialka.identyfikator}. Wyniki pojawią się po zakończeniu wszystkich kroków.`}
        </CardDescription>
        <CardAction className="flex items-center gap-2">
          {zakonczony ? (
            <>
              <Badge variant="sukces" className="animate-in fade-in zoom-in-90 duration-300">
                <CheckIcon data-icon="inline-start" />
                Gotowe
              </Badge>
              <Button variant="outline" size="sm" onClick={onPrzelacz}>
                {rozwiniety ? "Ukryj szczegóły" : "Pokaż szczegóły"}
                {rozwiniety ? <ChevronUpIcon data-icon="inline-end" /> : <ChevronDownIcon data-icon="inline-end" />}
              </Button>
            </>
          ) : (
            !blad && (
              <Button variant="ghost" size="sm" onClick={onPomin}>
                <FastForwardIcon data-icon="inline-start" />
                Pomiń animację
              </Button>
            )
          )}
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {blad && (
          <Alert variant="destructive" className="animate-in fade-in slide-in-from-top-1 duration-300">
            <AlertTitle>Wycena przerwana w kroku {biezacy.numer} · {biezacy.nazwa}</AlertTitle>
            <AlertDescription>{blad}</AlertDescription>
            <AlertAction>
              <Button size="sm" variant="outline" onClick={onWroc}>
                Wróć do danych
              </Button>
            </AlertAction>
          </Alert>
        )}

        {!zakonczony && <PasekPostepu postep={postep} biezacy={biezacy} blad={blad !== ""} />}

        {zakonczony && !rozwiniety ? (
          <PasekKrokow kroki={postep.kroki} />
        ) : (
          <Plotno postep={postep} zakonczony={zakonczony} blad={blad !== ""} />
        )}

        {!zakonczony && (
          <div className="grid grid-cols-[1fr_520px] gap-4">
            <BiezacyKrok key={biezacy.numer} krok={biezacy} podkrok={postep.podkrok} />
            <WycenianaDzialka dzialka={dzialka} granicaGotowa={postep.krok >= 2} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function PasekPostepu({ postep, biezacy, blad }: { postep: Postep; biezacy: KrokProcesu; blad: boolean }) {
  const udzialy = KROKI.map((_, i) => udzialKroku(i, postep, false))
  const procent = useLicznik((udzialy.reduce((a, b) => a + b, 0) / KROKI.length) * 100, 500, 0)

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <span className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">
            Krok {biezacy.numer} z {KROKI.length}
          </span>
          <span key={biezacy.numer} className="font-medium animate-in fade-in slide-in-from-bottom-1 duration-300">
            {biezacy.nazwa}
          </span>
        </span>
        <span className="text-sm font-medium">{liczba(procent)}%</span>
      </div>
      <div className="flex gap-1">
        {KROKI.map((k, i) => (
          <div key={k.numer} className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full transition-[width] duration-500 ease-out", blad && i === postep.krok ? "bg-spadek" : TLO[k.kolor])}
              style={{ width: `${udzialy[i] * 100}%` }}
            />
          </div>
        ))}
      </div>
    </div>
  )
}

function Plotno({ postep, zakonczony, blad }: { postep: Postep; zakonczony: boolean; blad: boolean }) {
  const krok = zakonczony ? KROKI.length : postep.krok

  return (
    <div className="plotno-kropki flex items-stretch rounded-sm border p-6 animate-in fade-in duration-300">
      {KROKI.map((k, i) => {
        let status: Status = "czeka"
        if (i < krok) {
          status = "gotowe"
        } else if (i === krok) {
          status = blad ? "blad" : "trwa"
        }
        return (
          <Fragment key={k.numer}>
            <Wezel krok={k} wynik={postep.kroki.find((w) => w.numer === k.numer)} status={status} />
            {i < KROKI.length - 1 && (
              <Lacznik
                kolor={k.kolor}
                kolorDalej={KROKI[i + 1].kolor}
                wypelniony={i < krok}
                plynie={i + 1 === krok && !zakonczony && !blad}
              />
            )}
          </Fragment>
        )
      })}
    </div>
  )
}

type PropsLacznika = {
  kolor: Kolor
  kolorDalej: Kolor
  wypelniony: boolean
  plynie: boolean
}

function Lacznik({ kolor, kolorDalej, wypelniony, plynie }: PropsLacznika) {
  return (
    <div className="relative mx-1 h-0.5 w-4 shrink-0 self-center bg-linia-mocna">
      <div
        className={cn("absolute inset-y-0 left-0 transition-[width] duration-500 ease-out", TLO[kolor])}
        style={{ width: wypelniony ? "100%" : "0%" }}
      />
      {plynie && (
        <span
          className={cn(
            "absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card animate-przeplyw",
            TLO[kolorDalej]
          )}
        />
      )}
    </div>
  )
}

type PropsWezla = {
  krok: KrokProcesu
  wynik: WynikKroku | undefined
  status: Status
}

function Wezel({ krok, wynik, status }: PropsWezla) {
  const czeka = status === "czeka"
  const trwa = status === "trwa"
  const gotowe = status === "gotowe"

  return (
    <div
      className={cn(
        "relative flex min-w-0 flex-1 flex-col gap-2.5 overflow-hidden rounded-sm border-2 bg-card p-3 transition-all duration-300 ease-out",
        czeka && "border-border",
        gotowe && "border-border shadow-xs",
        trwa && cn("-translate-y-1 shadow-md", RAMKA[krok.kolor]),
        status === "blad" && "border-spadek shadow-md"
      )}
    >
      <div className="flex items-start gap-2">
        <span
          className={cn(
            "flex size-6 shrink-0 items-center justify-center rounded-sm text-xs font-semibold text-white transition-colors duration-300",
            czeka ? "bg-linia-mocna" : TLO[krok.kolor],
            status === "blad" && "bg-spadek"
          )}
        >
          {gotowe ? <CheckIcon key="gotowe" className="size-3.5 animate-in zoom-in-50 duration-300" strokeWidth={3} /> : krok.numer}
        </span>
        <div className="min-w-0">
          <div className={cn("truncate text-sm font-medium transition-colors", czeka && "text-pomocniczy")}>{krok.nazwa}</div>
          <div className="line-clamp-2 text-xs text-muted-foreground">{krok.opis}</div>
        </div>
      </div>

      <div className="flex min-h-12 flex-1 items-center rounded-sm bg-muted px-2 py-1.5 text-xs" title={wynik?.wynik}>
        {wynik ? (
          <span className="line-clamp-2 font-medium animate-in fade-in slide-in-from-bottom-1 duration-300">{wynik.wynik}</span>
        ) : trwa ? (
          <span className={cn("flex items-center gap-1.5", TEKST[krok.kolor])}>
            <Spinner className="size-3" />
            Liczę…
          </span>
        ) : (
          <span className="text-pomocniczy">—</span>
        )}
      </div>

      <div className="flex items-center gap-1.5 text-xs">
        <span
          className={cn(
            "size-1.5 rounded-full transition-colors",
            gotowe && "bg-sukces",
            trwa && TLO[krok.kolor],
            status === "blad" && "bg-spadek",
            czeka && "bg-linia-mocna"
          )}
        />
        <span
          className={cn(
            "flex-1",
            gotowe && "text-sukces",
            trwa && TEKST[krok.kolor],
            status === "blad" && "text-spadek",
            czeka && "text-pomocniczy"
          )}
        >
          {gotowe ? "Gotowe" : trwa ? "W toku" : status === "blad" ? "Błąd" : "Oczekuje"}
        </span>
        <span className="text-pomocniczy">{wynik ? czas(wynik.czas) : "—"}</span>
      </div>

      {trwa && (
        <div className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden bg-muted">
          <div className={cn("h-full w-2/5 animate-skan", TLO[krok.kolor])} />
        </div>
      )}
    </div>
  )
}

function PasekKrokow({ kroki }: { kroki: WynikKroku[] }) {
  return (
    <div className="flex items-center rounded-sm bg-muted px-3 py-2.5 animate-in fade-in slide-in-from-top-1 duration-500">
      {KROKI.map((k, i) => {
        const wynik = kroki.find((w) => w.numer === k.numer)
        return (
          <div
            key={k.numer}
            className="flex flex-1 items-center gap-2 animate-in fade-in fill-mode-both duration-300"
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <IkonaModulu kolor={k.kolor} tekst={String(k.numer)} />
            <span className="text-sm font-medium whitespace-nowrap">{k.nazwa}</span>
            <span className="text-xs whitespace-nowrap text-pomocniczy">{wynik ? czas(wynik.czas) : "—"}</span>
            {i < KROKI.length - 1 && <ChevronRightIcon className="ml-auto size-4 text-pomocniczy" />}
          </div>
        )
      })}
    </div>
  )
}

function BiezacyKrok({ krok, podkrok }: { krok: KrokProcesu; podkrok: number }) {
  const gotowych = Math.min(podkrok, krok.podkroki.length)

  return (
    <div className="flex flex-col gap-3 rounded-sm border p-4 animate-in fade-in duration-300">
      <div className="flex items-center gap-2.5">
        <IkonaModulu kolor={krok.kolor} tekst={String(krok.numer)} />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">{krok.nazwa}</div>
          <div className="text-xs text-muted-foreground">{krok.opis}</div>
        </div>
        <span className="text-xs text-muted-foreground">
          {gotowych} z {krok.podkroki.length}
        </span>
      </div>

      <div className="flex flex-col gap-2 border-t pt-3">
        {krok.podkroki.map((opis, i) => {
          const gotowe = i < podkrok
          const trwa = i === podkrok
          return (
            <div
              key={opis}
              className="flex items-center gap-2.5 text-sm animate-in fade-in slide-in-from-left-2 fill-mode-both duration-300"
              style={{ animationDelay: `${i * 70}ms` }}
            >
              {gotowe && (
                <span className={cn("flex size-4 shrink-0 items-center justify-center rounded-sm text-white", TLO[krok.kolor])}>
                  <CheckIcon className="size-3 animate-in zoom-in-50 duration-200" strokeWidth={3} />
                </span>
              )}
              {trwa && <Spinner className={cn("size-4 shrink-0", TEKST[krok.kolor])} />}
              {!gotowe && !trwa && <span className="size-4 shrink-0 rounded-sm border-[1.5px] border-linia-mocna" />}
              <span className={cn("transition-colors duration-300", !gotowe && !trwa && "text-pomocniczy", trwa && "font-medium")}>
                {opis}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function WycenianaDzialka({ dzialka, granicaGotowa }: { dzialka: DaneDzialki; granicaGotowa: boolean }) {
  const wiersze = [
    ["Identyfikator", dzialka.zrodloGranicy === "rysunek" ? "granica narysowana" : dzialka.identyfikator],
    ["Gmina", dzialka.gmina],
    ["Rodzaj gruntu", nazwaOpcji(RODZAJE_GRUNTU, dzialka.rodzajGruntu)],
    ["Powierzchnia", `${liczba(Number(dzialka.powierzchnia.replace(",", ".")))} m²`],
    ["Data wyceny", data(dzialka.dataWyceny)],
  ]

  return (
    <div className="flex gap-4 rounded-sm border p-4">
      <MiniaturaDzialki granica={dzialka.granica} srodek={dzialka.srodek} gotowa={granicaGotowa} />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <span className="text-xs text-muted-foreground">Wyceniana działka</span>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
          {wiersze.map(([nazwa, wartosc]) => (
            <Fragment key={nazwa}>
              <dt className="text-muted-foreground">{nazwa}</dt>
              <dd className="text-right">{wartosc}</dd>
            </Fragment>
          ))}
        </dl>
      </div>
    </div>
  )
}

function MiniaturaDzialki({ granica, srodek, gotowa }: { granica: Granica; srodek: Punkt; gotowa: boolean }) {
  const punkty = granica.flatMap((wielokat) => wielokat.flat())
  if (punkty.length === 0) {
    return null
  }

  const szerokosc = punkty.reduce((suma, p) => suma + p[1], 0) / punkty.length
  const skrot = Math.cos((szerokosc * Math.PI) / 180)
  const xs = punkty.map((p) => p[0] * skrot)
  const ys = punkty.map((p) => -p[1])
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  const rozmiar = Math.max(Math.max(...xs) - minX, Math.max(...ys) - minY) || 1
  const skala = 80 / rozmiar
  const przesuniecieX = (100 - (Math.max(...xs) - minX) * skala) / 2
  const przesuniecieY = (100 - (Math.max(...ys) - minY) * skala) / 2
  const naEkran = (p: number[]) => [(p[0] * skrot - minX) * skala + przesuniecieX, (-p[1] - minY) * skala + przesuniecieY]

  const sciezka = granica
    .flatMap((wielokat) =>
      wielokat.map((pierscien) => "M" + pierscien.map((p) => naEkran(p).map((v) => v.toFixed(2)).join(",")).join("L") + "Z")
    )
    .join("")
  const [srodekX, srodekY] = naEkran(srodek)

  return (
    <svg viewBox="0 0 100 100" className="size-36 shrink-0 rounded-sm border bg-muted">
      <path d={sciezka} className="fill-card animate-in fade-in fill-mode-both delay-700 duration-500" />
      <path
        d={sciezka}
        pathLength={1}
        strokeDasharray={1}
        strokeWidth={1.5}
        strokeLinejoin="round"
        className="fill-none stroke-akcja animate-rysuj"
      />
      {gotowa && (
        <g className="origin-center animate-in zoom-in-0 duration-300 transform-fill">
          <circle cx={srodekX} cy={srodekY} r={3.5} className="fill-card stroke-akcja" strokeWidth={1.2} />
          <circle cx={srodekX} cy={srodekY} r={1.6} className="fill-akcja" />
        </g>
      )}
    </svg>
  )
}
