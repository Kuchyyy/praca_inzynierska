import { useState } from "react"
import { ArrowRightIcon, BookOpenIcon, SearchIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { KOLOR_GRUPY } from "@/lib/kolory"
import { liczba } from "@/lib/format"
import { czyFlaga, pokazWartosc } from "@/lib/cechy"
import { OPISY_CECH, ROZDZIALY, opisCechy } from "@/dane/opisyCech"
import type { OpisModelu } from "@/typy"
import { IkonaModulu } from "./IkonaModulu"

type Props = {
  wybrana: string
  onWybierz: (kod: string) => void
  model: OpisModelu | null
  onPelnyOpis: (kod: string) => void
}

export function SlownikCech({ wybrana, onWybierz, model, onPelnyOpis }: Props) {
  const [szukane, setSzukane] = useState("")

  const opis = opisCechy(wybrana)
  const rozdzial = ROZDZIALY.find((r) => r.kod === opis.rozdzial)
  const fraza = szukane.trim().toLowerCase()
  const pasujace = fraza
    ? OPISY_CECH.filter((o) => o.nazwa.toLowerCase().includes(fraza) || o.kod.includes(fraza))
    : []

  // Miejsce cechy w rankingu ważności modelu, z którego pochodzi wynik główny.
  let miejsce = "—"
  let mediana = "—"
  let braki = "—"
  if (model) {
    const waznosc = model.waznosc[model.najlepszy] ?? {}
    const ranking = Object.keys(waznosc).sort((a, b) => waznosc[b] - waznosc[a])
    if (ranking.includes(opis.kod)) {
      miejsce = `#${ranking.indexOf(opis.kod) + 1} z ${ranking.length}`
    }
    const statystyka = model.statystyki[opis.kod]
    if (statystyka) {
      braki = `${liczba(statystyka.braki_procent, 1)}%`
      if (czyFlaga(opis.kod)) {
        mediana = `1 w ${liczba((statystyka.srednia ?? 0) * 100, 1)}%`
      } else if (statystyka.mediana !== null) {
        mediana = pokazWartosc(opis.kod, statystyka.mediana)
      }
    }
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2.5">
          <IkonaModulu kolor="akcja" ikona={BookOpenIcon} />
          Słownik cech
        </CardTitle>
        <CardDescription className="pl-8.5">Co oznacza cecha i skąd się bierze</CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={szukane}
            onChange={(e) => setSzukane(e.target.value)}
            placeholder={`Szukaj wśród ${OPISY_CECH.length} cech…`}
            className="pl-8"
          />
        </div>

        {pasujace.length > 0 && (
          <div className="flex max-h-60 flex-col overflow-y-auto rounded-sm border">
            {pasujace.map((o) => (
              <Button
                key={o.kod}
                variant="ghost"
                className="justify-start rounded-none"
                onClick={() => {
                  onWybierz(o.kod)
                  setSzukane("")
                }}
              >
                {o.nazwa}
              </Button>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-3 rounded-sm bg-muted p-4">
          <div className="flex items-start gap-2">
            <span className="flex-1 text-base font-semibold">{opis.nazwa}</span>
            <Badge variant={KOLOR_GRUPY[opis.grupa]}>{rozdzial?.nazwa ?? opis.rozdzial}</Badge>
          </div>
          <span className="-mt-2 font-mono text-xs text-muted-foreground">{opis.kod}</span>

          <Akapit tytul="Co to jest" tresc={opis.coTo} />
          <Akapit tytul="Jak liczona" tresc={opis.wzor ?? opis.kroki[opis.kroki.length - 1] ?? "—"} />
          <Akapit tytul="Źródło i jednostka" tresc={opis.zrodlo} />

          <div className="grid grid-cols-3 gap-2">
            <Statystyka nazwa="Ważność" wartosc={miejsce} />
            <Statystyka nazwa="Mediana w treningu" wartosc={mediana} />
            <Statystyka nazwa="Braki" wartosc={braki} />
          </div>

          <Button variant="outline" className="self-start bg-card" onClick={() => onPelnyOpis(opis.kod)}>
            Pełny opis cechy
            <ArrowRightIcon data-icon="inline-end" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function Akapit({ tytul, tresc }: { tytul: string; tresc: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-pomocniczy">{tytul}</span>
      <p className="text-sm">{tresc}</p>
    </div>
  )
}

function Statystyka({ nazwa, wartosc }: { nazwa: string; wartosc: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-sm border bg-card p-2">
      <span className="text-xs text-muted-foreground">{nazwa}</span>
      <span className="text-xs font-medium">{wartosc}</span>
    </div>
  )
}
