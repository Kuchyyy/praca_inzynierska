import { useState } from "react"
import { ChartBarIcon } from "lucide-react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { cn } from "@/lib/utils"
import { zaM2, zeZnakiem } from "@/lib/format"
import { pokazWartosc } from "@/lib/cechy"
import { opisCechy } from "@/dane/opisyCech"
import type { Cechy, Wyjasnienie } from "@/typy"
import { IkonaModulu } from "./IkonaModulu"

const POKAZANE = 8

const METODA: Record<string, string> = {
  "Linear Regression": "rozkład liniowy względem średniej działki z treningu",
  "Bayesian Ridge": "rozkład liniowy względem średniej działki z treningu",
  "Decision Tree": "wartości SHAP",
  "Random Forest": "wartości SHAP",
  "Gradient Boosting": "wartości SHAP",
}

type Props = {
  wyjasnienia: Wyjasnienie[]
  cechy: Cechy
  waznosc: Record<string, Record<string, number>>
  najlepszy: string
}

export function WplywCech({ wyjasnienia, cechy, waznosc, najlepszy }: Props) {
  const [model, setModel] = useState(najlepszy)

  const wyjasnienie = wyjasnienia.find((w) => w.model === model) ?? wyjasnienia[0]
  const pokazane = wyjasnienie.wklady.slice(0, POKAZANE)
  const reszta = wyjasnienie.wklady.slice(POKAZANE)
  const sumaReszty = reszta.reduce((suma, w) => suma + w.wklad, 0)
  const wiersze = [
    ...pokazane.map((w) => ({
      kod: w.kod,
      nazwa: opisCechy(w.kod).nazwa,
      wartosc: pokazWartosc(w.kod, cechy[w.kod]),
      wklad: w.wklad,
    })),
    { kod: "reszta", nazwa: `Pozostałe ${reszta.length} cech`, wartosc: "", wklad: sumaReszty },
  ]
  const najwiekszyWklad = Math.max(...wiersze.map((w) => Math.abs(w.wklad)), 0.01)

  const waznoscModelu = waznosc[model] ?? {}
  const ranking = Object.entries(waznoscModelu)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
  const najwiekszaWaznosc = Math.max(...ranking.map(([, w]) => w), 0.01)

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2.5">
          <IkonaModulu kolor="wynik" ikona={ChartBarIcon} />
          Wpływ cech na tę wycenę
        </CardTitle>
        <CardDescription className="pl-8.5">
          Co podniosło, a co obniżyło cenę względem przeciętnej działki z treningu
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <ToggleGroup
          variant="wybor"
          size="sm"
          spacing={1}
          value={[model]}
          onValueChange={(v) => v.length > 0 && setModel(String(v[0]))}
          className="flex-wrap"
        >
          {wyjasnienia.map((w) => (
            <ToggleGroupItem key={w.model} value={w.model}>
              {w.model}
              {w.model === najlepszy && " ★"}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>

        <Tabs defaultValue="wycena" className="gap-4">
          <TabsList>
            <TabsTrigger value="wycena">Ta wycena</TabsTrigger>
            <TabsTrigger value="globalnie">Ważność globalna</TabsTrigger>
          </TabsList>

          <TabsContent value="wycena" className="flex flex-col gap-3">
            <div className="flex justify-between rounded-sm bg-muted px-3 py-2 text-xs">
              <span className="text-muted-foreground">Punkt startowy: przeciętna wycena modelu w treningu</span>
              <span className="font-medium">{zaM2(wyjasnienie.start)}</span>
            </div>

            {wiersze.map((w) => {
              const szerokosc = (Math.abs(w.wklad) / najwiekszyWklad) * 50
              const wzrost = w.wklad > 0
              return (
                <div key={w.kod} className="flex items-center gap-3">
                  <div className="flex w-56 shrink-0 flex-col">
                    <span className="text-sm">{w.nazwa}</span>
                    {w.wartosc && <span className="text-xs text-pomocniczy">{w.wartosc}</span>}
                  </div>
                  <div className="relative h-4 flex-1">
                    <div className="absolute inset-y-0 left-1/2 w-px bg-linia-mocna" />
                    <div
                      className={cn("absolute top-0.5 h-3", wzrost ? "bg-sukces" : "bg-spadek")}
                      style={wzrost ? { left: "50%", width: `${szerokosc}%` } : { right: "50%", width: `${szerokosc}%` }}
                    />
                  </div>
                  <span
                    className={cn("w-16 text-right text-xs font-medium", wzrost ? "text-sukces" : "text-spadek")}
                  >
                    {zeZnakiem(w.wklad)}
                  </span>
                </div>
              )
            })}

            <Separator />
            <div className="flex justify-between text-sm font-medium">
              <span>Wycena modelu {wyjasnienie.model}</span>
              <span>{zaM2(wyjasnienie.cena)}</span>
            </div>
            <span className="text-xs text-muted-foreground">
              Wkłady w zł/m², metoda: {METODA[wyjasnienie.model] ?? "wartości SHAP"}. Start plus suma wkładów daje
              dokładnie wycenę modelu. ★ oznacza model, z którego pochodzi wynik główny.
            </span>
          </TabsContent>

          <TabsContent value="globalnie" className="flex flex-col gap-3">
            <span className="text-xs text-muted-foreground">
              O ile zł/m² rośnie błąd MAE modelu {model}, gdy wartości cechy się przetasuje (próbka testu).
            </span>
            {ranking.length === 0 && <span className="text-sm text-muted-foreground">Brak danych o ważności.</span>}
            {ranking.map(([kod, wartosc]) => (
              <div key={kod} className="flex items-center gap-3">
                <span className="w-56 shrink-0 text-sm">{opisCechy(kod).nazwa}</span>
                <div className="h-3 flex-1 bg-muted">
                  <div
                    className="h-full bg-primary"
                    style={{ width: `${(Math.max(wartosc, 0) / najwiekszaWaznosc) * 100}%` }}
                  />
                </div>
                <span className="w-20 text-right text-xs font-medium">{zeZnakiem(wartosc)}</span>
              </div>
            ))}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
