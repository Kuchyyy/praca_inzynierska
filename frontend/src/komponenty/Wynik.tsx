import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { liczba, zaM2, zlotych } from "@/lib/format"
import { RODZAJE_GRUNTU, nazwaOpcji } from "@/dane/slowniki"
import type { DaneDzialki, Uwaga, Wycena } from "@/typy"
import { IkonaModulu } from "./IkonaModulu"

type Props = {
  dzialka: DaneDzialki
  // Bieżąca wycena (po zmianach cech) i wycena modelu na wyliczonych cechach.
  wycena: Wycena
  bazowa: Wycena
  uwagi: Uwaga[]
}

const KOLOR_PEWNOSCI: Record<string, "sukces" | "ostrzezenie" | "spadek"> = {
  "Wysoka pewność": "sukces",
  "Średnia pewność": "ostrzezenie",
  "Niska pewność": "spadek",
}

export function Wynik({ dzialka, wycena, bazowa, uwagi }: Props) {
  const powierzchnia = Number(dzialka.powierzchnia.replace(",", "."))
  const zmieniona = Math.abs(wycena.cenaM2 - bazowa.cenaM2) > 0.005

  // Skala paska: trochę szersza niż przedział, żeby było widać jego krańce.
  const skalaOd = wycena.przedzialOd * 0.85
  const skalaDo = wycena.przedzialDo * 1.15
  const procent = (wartosc: number) => ((wartosc - skalaOd) / (skalaDo - skalaOd)) * 100

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2.5">
          <IkonaModulu kolor="wynik" />
          Wynik wyceny
        </CardTitle>
        <CardDescription className="pl-8.5">
          {wycena.model} · {nazwaOpcji(RODZAJE_GRUNTU, dzialka.rodzajGruntu).toLowerCase()}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-5xl font-medium tracking-tight">{zlotych(wycena.cenaM2 * powierzchnia)}</span>
          <span className="text-sm text-muted-foreground">
            {zaM2(wycena.cenaM2)} · {liczba(powierzchnia)} m²
          </span>
          {zmieniona && (
            <span className="text-xs text-ostrzezenie">
              Po zmianie cech. Wycena na wyliczonych cechach: {zaM2(bazowa.cenaM2)}
            </span>
          )}
        </div>

        <div className="flex flex-col gap-2.5 rounded-sm bg-muted p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Przedział 80%</span>
            <Badge variant={KOLOR_PEWNOSCI[wycena.pewnosc] ?? "ostrzezenie"}>{wycena.pewnosc}</Badge>
          </div>
          <div className="relative h-2 bg-border">
            <div
              className="absolute inset-y-0 bg-wynik"
              style={{
                left: `${procent(wycena.przedzialOd)}%`,
                width: `${procent(wycena.przedzialDo) - procent(wycena.przedzialOd)}%`,
              }}
            />
            <div
              className="absolute inset-y-0 w-0.75 bg-primary"
              style={{ left: `${Math.min(Math.max(procent(wycena.cenaM2), 0), 100)}%` }}
            />
          </div>
          <div className="flex justify-between font-mono text-xs">
            <span>{zlotych(wycena.przedzialOd * powierzchnia)}</span>
            <span>{zlotych(wycena.przedzialDo * powierzchnia)}</span>
          </div>
          <span className="text-xs text-muted-foreground">
            {zaM2(wycena.przedzialOd)} – {zaM2(wycena.przedzialDo)}. Tak rozrzucone były prawdziwe ceny na
            zbiorze testowym przy {wycena.koszyk === 0 ? "braku transakcji" : `${wycena.koszyk}+ transakcjach`} w 2 km.
          </span>
        </div>

        <ul className="flex flex-col gap-1.5">
          {uwagi.map((uwaga) => (
            <li key={uwaga.tekst} className="flex items-center gap-2 text-xs">
              <span className={cn("size-1.5 shrink-0 rounded-full", uwaga.dobrze ? "bg-sukces" : "bg-ostrzezenie")} />
              {uwaga.tekst}
            </li>
          ))}
        </ul>
      </CardContent>

      <CardFooter className="pb-4 text-xs text-muted-foreground">
        Model uczył się na cenach transakcyjnych z RCN, czyli kwotach z aktów notarialnych. Ceny ofertowe
        z ogłoszeń są zwykle wyższe.
      </CardFooter>
    </Card>
  )
}
