import { ChartLineIcon } from "lucide-react"
import { Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, XAxis, YAxis } from "recharts"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { liczba, zaM2 } from "@/lib/format"
import type { HistoriaGminy } from "@/typy"
import { IkonaModulu } from "./IkonaModulu"

const KONFIGURACJA = {
  mediana: { label: "Mediana zł/m²", color: "var(--sukces)" },
  liczba: { label: "Liczba transakcji", color: "var(--linia-mocna)" },
} satisfies ChartConfig

const MIESIACE = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]

type Props = {
  gmina: string
  historia: HistoriaGminy
  trend: number | null
  cenaM2: number
}

export function HistoriaCen({ gmina, historia, trend, cenaM2 }: Props) {
  // Miesiąc z backendu ma postać „2025-03”, na osi pokazujemy „III 2025”.
  const punkty = historia.punkty.map((p) => {
    const [rok, miesiac] = p.miesiac.split("-")
    return { ...p, miesiac: `${MIESIACE[Number(miesiac) - 1]} ${rok}` }
  })
  const najwyzsza = Math.max(cenaM2, ...punkty.map((p) => p.mediana))
  const najwiecej = Math.max(1, ...punkty.map((p) => p.liczba))

  const kafelki = [
    {
      nazwa: "Mediana 12 mies.",
      wartosc: historia.medianaTeraz === null ? "brak" : zaM2(historia.medianaTeraz),
      kolor: "",
    },
    {
      nazwa: "Zmiana r/r",
      wartosc: trend === null ? "brak" : `${trend > 0 ? "+" : ""}${liczba(trend * 100, 1)}%`,
      kolor: trend === null ? "" : trend >= 0 ? "text-sukces" : "text-spadek",
    },
    { nazwa: "Transakcje w gminie", wartosc: liczba(historia.transakcje), kolor: "" },
  ]

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2.5">
          <IkonaModulu kolor="sukces" ikona={ChartLineIcon} />
          Historia cen okolicy
        </CardTitle>
        <CardDescription className="pl-8.5">
          Mediana ceny za m² w gminie {gmina}, ostatnie 24 miesiące przed datą wyceny
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="flex gap-8">
          {kafelki.map((k) => (
            <div key={k.nazwa} className="flex flex-col gap-0.5">
              <span className="text-xs text-muted-foreground">{k.nazwa}</span>
              <span className={`text-base font-semibold ${k.kolor}`}>{k.wartosc}</span>
            </div>
          ))}
        </div>

        {punkty.length === 0 ? (
          <div className="flex h-64 items-center justify-center rounded-sm bg-muted text-sm text-muted-foreground">
            Brak transakcji w gminie w ostatnich 24 miesiącach
          </div>
        ) : (
          <ChartContainer config={KONFIGURACJA} className="h-64 w-full">
            <ComposedChart data={punkty} margin={{ top: 16, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="miesiac" tickLine={false} axisLine={false} interval={5} />
              <YAxis yAxisId="cena" domain={[0, Math.ceil(najwyzsza * 1.15)]} tickLine={false} axisLine={false} width={44} />
              <YAxis yAxisId="liczba" orientation="right" hide domain={[0, najwiecej * 3]} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar yAxisId="liczba" dataKey="liczba" fill="var(--color-liczba)" barSize={10} />
              <Line yAxisId="cena" dataKey="mediana" stroke="var(--color-mediana)" strokeWidth={2} dot={false} />
              <ReferenceLine
                yAxisId="cena"
                y={cenaM2}
                stroke="var(--wynik)"
                label={{ value: `Ta działka: ${zaM2(cenaM2)}`, position: "insideTopLeft", fill: "var(--wynik)", fontSize: 12 }}
              />
            </ComposedChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  )
}
