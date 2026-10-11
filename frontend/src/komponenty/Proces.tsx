import { ArrowRightIcon, CheckIcon, ChevronDownIcon, ChevronRightIcon, ChevronUpIcon } from "lucide-react"

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
import { Progress } from "@/components/ui/progress"
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { RAMKA } from "@/lib/kolory"
import { KROKI } from "@/dane/kroki"
import { RODZAJE_GRUNTU, nazwaOpcji } from "@/dane/slowniki"
import { czas, liczba } from "@/lib/format"
import type { DaneDzialki, KrokProcesu, Postep, WynikKroku } from "@/typy"
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
}

export function Proces({ dzialka, postep, blad, czasRazem, zakonczony, rozwiniety, onPrzelacz, onWroc }: Props) {
  const biezacy = KROKI[Math.min(postep.krok, KROKI.length - 1)]
  const procent = zakonczony
    ? 100
    : ((postep.krok + Math.min(postep.podkrok / biezacy.podkroki.length, 1)) / KROKI.length) * 100

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2.5">
          <IkonaModulu kolor="akcja" />
          Proces wyceny
        </CardTitle>
        <CardDescription className="pl-8.5">
          {zakonczony && czasRazem !== null
            ? `Wszystkie kroki zakończone · ${czas(czasRazem)}`
            : `Liczę wycenę działki ${dzialka.identyfikator}. Wyniki pojawią się po zakończeniu wszystkich kroków.`}
        </CardDescription>
        {zakonczony && (
          <CardAction className="flex items-center gap-2">
            <Badge variant="sukces">Gotowe</Badge>
            <Button variant="outline" size="sm" onClick={onPrzelacz}>
              {rozwiniety ? "Ukryj szczegóły" : "Pokaż szczegóły"}
              {rozwiniety ? <ChevronUpIcon data-icon="inline-end" /> : <ChevronDownIcon data-icon="inline-end" />}
            </Button>
          </CardAction>
        )}
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {blad && (
          <Alert variant="destructive">
            <AlertTitle>Wycena przerwana w kroku {biezacy.numer} · {biezacy.nazwa}</AlertTitle>
            <AlertDescription>{blad}</AlertDescription>
            <AlertAction>
              <Button size="sm" variant="outline" onClick={onWroc}>
                Wróć do danych
              </Button>
            </AlertAction>
          </Alert>
        )}

        {!zakonczony && !blad && (
          <div className="flex flex-col gap-2">
            <div className="flex justify-between text-sm">
              <span className="font-medium">
                Krok {biezacy.numer} z {KROKI.length} · {biezacy.nazwa}
              </span>
              <span className="font-mono text-xs text-muted-foreground">{liczba(procent)}%</span>
            </div>
            <Progress value={procent} />
          </div>
        )}

        {zakonczony && !rozwiniety ? (
          <PasekKrokow kroki={postep.kroki} />
        ) : (
          <Plotno postep={postep} zakonczony={zakonczony} blad={blad !== ""} />
        )}

        {!zakonczony && (
          <div className="grid grid-cols-[1fr_420px] gap-4">
            <BiezacyKrok krok={biezacy} podkrok={postep.podkrok} />
            <WycenianaDzialka dzialka={dzialka} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// Pełny widok: płótno w kropki i sześć węzłów połączonych strzałkami.
function Plotno({ postep, zakonczony, blad }: { postep: Postep; zakonczony: boolean; blad: boolean }) {
  const krok = zakonczony ? KROKI.length : postep.krok
  return (
    <div className="plotno-kropki flex items-center gap-2 rounded-sm border p-6">
      {KROKI.map((k, i) => (
        <div key={k.numer} className="flex flex-1 items-center gap-2">
          <Wezel
            krok={k}
            wynik={postep.kroki.find((w) => w.numer === k.numer)}
            status={i < krok ? "gotowe" : i === krok ? (blad ? "blad" : "trwa") : "czeka"}
          />
          {i < KROKI.length - 1 && <ArrowRightIcon className="size-4 shrink-0 text-linia-mocna" />}
        </div>
      ))}
    </div>
  )
}

type PropsWezla = {
  krok: KrokProcesu
  wynik: WynikKroku | undefined
  status: "gotowe" | "trwa" | "blad" | "czeka"
}

function Wezel({ krok, wynik, status }: PropsWezla) {
  const czeka = status === "czeka"

  return (
    <div
      className={cn(
        "flex min-w-0 flex-1 flex-col gap-2.5 rounded-sm border bg-card p-3 shadow-xs",
        status === "trwa" && "border-2 border-akcja",
        status === "blad" && "border-2 border-spadek",
        status === "gotowe" && krok.numer === KROKI.length && cn("border-2", RAMKA[krok.kolor])
      )}
    >
      <div className="flex items-center gap-2">
        {czeka ? (
          <span className="flex size-6 shrink-0 items-center justify-center rounded-sm bg-linia-mocna font-mono text-xs text-white">
            {krok.numer}
          </span>
        ) : (
          <IkonaModulu kolor={krok.kolor} tekst={String(krok.numer)} />
        )}
        <div className="min-w-0">
          <div className={cn("truncate text-sm font-medium", czeka && "text-pomocniczy")}>{krok.nazwa}</div>
          <div className="truncate text-xs text-muted-foreground">{krok.opis}</div>
        </div>
      </div>

      <div className="min-h-9 truncate rounded-sm bg-muted px-2 py-1.5 font-mono text-xs" title={wynik?.wynik}>
        {wynik ? wynik.wynik : <span className="text-pomocniczy">—</span>}
      </div>

      <div className="flex items-center gap-1.5 text-xs">
        <span
          className={cn(
            "size-1.5 rounded-full",
            status === "gotowe" && "bg-sukces",
            status === "trwa" && "bg-akcja",
            status === "blad" && "bg-spadek",
            czeka && "bg-linia-mocna"
          )}
        />
        <span
          className={cn(
            "flex-1",
            status === "gotowe" && "text-sukces",
            status === "trwa" && "text-akcja",
            status === "blad" && "text-spadek",
            czeka && "text-pomocniczy"
          )}
        >
          {status === "gotowe" ? "Gotowe" : status === "trwa" ? "Liczę…" : status === "blad" ? "Błąd" : "Oczekuje"}
        </span>
        <span className="font-mono text-pomocniczy">{wynik ? czas(wynik.czas) : "—"}</span>
      </div>
    </div>
  )
}

// Zwinięty widok po wycenie: jeden pasek z krokami i prawdziwymi czasami.
function PasekKrokow({ kroki }: { kroki: WynikKroku[] }) {
  return (
    <div className="flex items-center rounded-sm bg-muted px-3 py-2.5">
      {KROKI.map((k, i) => {
        const wynik = kroki.find((w) => w.numer === k.numer)
        return (
          <div key={k.numer} className="flex flex-1 items-center gap-2">
            <IkonaModulu kolor={k.kolor} tekst={String(k.numer)} />
            <span className="text-sm font-medium whitespace-nowrap">{k.nazwa}</span>
            <span className="font-mono text-xs whitespace-nowrap text-pomocniczy">{wynik ? czas(wynik.czas) : "—"}</span>
            {i < KROKI.length - 1 && <ChevronRightIcon className="ml-auto size-4 text-pomocniczy" />}
          </div>
        )
      })}
    </div>
  )
}

function BiezacyKrok({ krok, podkrok }: { krok: KrokProcesu; podkrok: number }) {
  return (
    <div className="flex flex-col gap-2.5 rounded-sm border p-4">
      <span className="text-xs text-muted-foreground">Co się teraz dzieje</span>
      {krok.podkroki.map((opis, i) => {
        const gotowe = i < podkrok
        const trwa = i === podkrok
        return (
          <div key={opis} className="flex items-center gap-2.5 text-sm">
            <span
              className={cn(
                "flex size-4 shrink-0 items-center justify-center rounded-sm",
                gotowe && "bg-sukces text-white",
                trwa && "bg-akcja",
                !gotowe && !trwa && "border-[1.5px] border-linia-mocna"
              )}
            >
              {gotowe && <CheckIcon className="size-3" />}
              {trwa && <span className="size-1.5 bg-white" />}
            </span>
            <span className={cn(!gotowe && !trwa && "text-pomocniczy")}>{opis}</span>
          </div>
        )
      })}
    </div>
  )
}

function WycenianaDzialka({ dzialka }: { dzialka: DaneDzialki }) {
  const wiersze = [
    ["Identyfikator", dzialka.zrodloGranicy === "rysunek" ? "granica narysowana" : dzialka.identyfikator],
    ["Obręb", dzialka.obreb],
    ["Gmina", dzialka.gmina],
    ["Rodzaj gruntu", nazwaOpcji(RODZAJE_GRUNTU, dzialka.rodzajGruntu)],
    ["Powierzchnia", `${liczba(Number(dzialka.powierzchnia.replace(",", ".")))} m²`],
    ["Data wyceny", dzialka.dataWyceny],
  ]

  return (
    <div className="flex flex-col gap-1 rounded-sm border p-4">
      <span className="text-xs text-muted-foreground">Wyceniana działka</span>
      <Table>
        <TableBody>
          {wiersze.map(([nazwa, wartosc]) => (
            <TableRow key={nazwa} className="border-0">
              <TableCell className="px-0 py-1.5 text-muted-foreground">{nazwa}</TableCell>
              <TableCell className="px-0 py-1.5 text-right font-mono">{wartosc}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
