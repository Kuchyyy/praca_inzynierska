import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { liczba, zaM2 } from "@/lib/format"
import type { WynikModelu } from "@/typy"
import { IkonaModulu } from "./IkonaModulu"

type Props = {
  modele: WynikModelu[]
  najlepszy: string
  testOd: string
}

export function PorownanieModeli({ modele, najlepszy, testOd }: Props) {
  const najwyzsza = Math.max(...modele.map((m) => m.cenaM2))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2.5">
          <IkonaModulu kolor="model" />
          Porównanie modeli
        </CardTitle>
        <CardDescription className="pl-8.5">Ta sama działka, {modele.length} modeli</CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-3.5">
        {modele.map((model) => {
          const glowny = model.nazwa === najlepszy
          return (
            <div key={model.nazwa} className="flex flex-col gap-1.5">
              <div className="flex items-center gap-3 text-sm">
                <span className={cn("flex-1", glowny && "font-medium")}>{model.nazwa}</span>
                <span className="font-mono text-xs text-pomocniczy">
                  MAE {liczba(model.mae, 1)} · R² {liczba(model.r2, 2)}
                </span>
                <span className="w-28 text-right font-mono text-xs font-medium">{zaM2(model.cenaM2)}</span>
              </div>
              <div className="h-1.5 bg-muted">
                <div
                  className={cn("h-full", glowny ? "bg-model" : "bg-linia-mocna")}
                  style={{ width: `${(model.cenaM2 / (najwyzsza * 1.08)) * 100}%` }}
                />
              </div>
            </div>
          )
        })}
      </CardContent>

      <CardFooter className="pb-4 text-xs text-muted-foreground">
        MAE w zł/m² i R² na zbiorze testowym (transakcje od {testOd}). Wynik główny pochodzi z modelu o
        najniższym MAE.
      </CardFooter>
    </Card>
  )
}
