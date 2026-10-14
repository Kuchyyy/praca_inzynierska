import { useState } from "react"
import { TableIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { cn } from "@/lib/utils"
import { KOLOR_GRUPY, TLO } from "@/lib/kolory"
import { zaM2 } from "@/lib/format"
import { czyFlaga, pokazWartosc } from "@/lib/cechy"
import { OPISY_CECH, TYLKO_DO_ODCZYTU } from "@/dane/opisyCech"
import type { Cechy, GrupaCechy } from "@/typy"
import { IkonaModulu } from "./IkonaModulu"

const NAZWY_GRUP: Record<GrupaCechy, string> = {
  sasiedztwo: "Sąsiedztwo",
  osm: "OSM",
  dzialka: "Działka",
  przeznaczenie: "Przeznaczenie",
}

type Props = {
  cechy: Cechy
  naTle: { obszar: "gmina" | "powiat"; percentyle: Record<string, number | null> }
  cenaM2: number
  // Wycena po zmianie cech albo null, gdy pokazujemy wycenę na wyliczonych cechach.
  przeliczona: number | null
  onPrzelicz: (cechy: Cechy | null) => Promise<void>
}

export function CechyDzialki({ cechy, naTle, cenaM2, przeliczona, onPrzelicz }: Props) {
  const [grupa, setGrupa] = useState("wszystkie")
  // Wpisane wartości trzymamy jako tekst, żeby dało się wpisać np. „0,”.
  const [wpisane, setWpisane] = useState<Record<string, string>>({})
  // Wpisy, z którymi liczono ostatnie przeliczenie.
  const [przeliczone, setPrzeliczone] = useState<Record<string, string>>({})
  const [liczy, setLiczy] = useState(false)
  const [blad, setBlad] = useState("")

  const wszystkie = OPISY_CECH.filter((o) => o.kod in cechy)
  const widoczne = wszystkie.filter((o) => grupa === "wszystkie" || o.grupa === grupa)
  const grupy = [
    { kod: "wszystkie", nazwa: `Wszystkie ${wszystkie.length}` },
    ...(Object.keys(NAZWY_GRUP) as GrupaCechy[]).map((g) => ({
      kod: g,
      nazwa: `${NAZWY_GRUP[g]} ${wszystkie.filter((o) => o.grupa === g).length}`,
    })),
  ]

  function liczbaZPola(kod: string) {
    const tekst = wpisane[kod]
    if (tekst === undefined) {
      return cechy[kod]
    }
    if (tekst.trim() === "") {
      return null
    }
    const wartosc = Number(tekst.replace(/\s/g, "").replace(",", "."))
    return Number.isFinite(wartosc) ? wartosc : cechy[kod]
  }

  const poZmianach: Cechy = {}
  for (const kod of Object.keys(cechy)) {
    poZmianach[kod] = liczbaZPola(kod)
  }
  const zmienione = Object.keys(cechy).filter((kod) => poZmianach[kod] !== cechy[kod])
  const czekaNaPrzeliczenie = JSON.stringify(wpisane) !== JSON.stringify(przeliczone)

  async function przelicz() {
    setLiczy(true)
    setBlad("")
    try {
      await onPrzelicz(zmienione.length > 0 ? poZmianach : null)
      setPrzeliczone(wpisane)
    } catch (e) {
      setBlad(e instanceof Error ? e.message : String(e))
    } finally {
      setLiczy(false)
    }
  }

  async function przywroc() {
    setWpisane({})
    setPrzeliczone({})
    setBlad("")
    await onPrzelicz(null)
  }

  let stopka = `${wszystkie.length} cech policzonych dla tej działki. Zmień wartość i przelicz, żeby zobaczyć, jak reaguje model.`
  if (blad) {
    stopka = blad
  } else if (czekaNaPrzeliczenie && zmienione.length > 0) {
    stopka = `Zmieniono ${zmienione.length} ${zmienione.length === 1 ? "cechę" : "cechy"}. Kliknij „Przelicz”.`
  } else if (przeliczona !== null) {
    const roznica = ((przeliczona - cenaM2) / cenaM2) * 100
    stopka = `Nowa wycena: ${zaM2(przeliczona)} (${roznica > 0 ? "+" : ""}${roznica.toFixed(1).replace(".", ",")}%)`
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2.5">
          <IkonaModulu kolor="ostrzezenie" ikona={TableIcon} />
          Cechy działki
        </CardTitle>
        <CardDescription className="pl-8.5">
          Wszystkie wartości, które dostał model. Możesz je zmienić i przeliczyć
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        <ToggleGroup
          variant="wybor"
          size="sm"
          spacing={1}
          value={[grupa]}
          onValueChange={(v) => v.length > 0 && setGrupa(String(v[0]))}
        >
          {grupy.map((g) => (
            <ToggleGroupItem key={g.kod} value={g.kod}>
              {g.nazwa}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>

        <div className="max-h-160 overflow-y-auto">
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-card">
              <TableRow>
                <TableHead className="px-0 text-xs text-pomocniczy">Cecha</TableHead>
                <TableHead className="w-32 text-xs text-pomocniczy">Wartość</TableHead>
                <TableHead className="w-32 text-xs text-pomocniczy">Na tle {naTle.obszar === "gmina" ? "gminy" : "powiatu"}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {widoczne.map((opis) => {
                const kod = opis.kod
                const doOdczytu = TYLKO_DO_ODCZYTU.includes(kod)
                const nowa = liczbaZPola(kod)
                const zmieniona = nowa !== cechy[kod]
                const percentyl = naTle.percentyle[kod]
                const wartosc = cechy[kod]
                return (
                  <TableRow key={kod} className={cn(zmieniona && "bg-muted")}>
                    <TableCell className={cn("px-0 whitespace-normal", zmieniona && "pl-2")}>
                      <div className="flex items-center gap-2">
                        <span className={cn("size-1.5 shrink-0", TLO[KOLOR_GRUPY[opis.grupa]])} />
                        <span>{opis.nazwa}</span>
                      </div>
                      <span className={cn("font-mono text-xs break-all", zmieniona ? "text-ostrzezenie" : "text-pomocniczy")}>
                        {kod}
                        {zmieniona && ` · było ${pokazWartosc(kod, wartosc)}`}
                      </span>
                    </TableCell>
                    <TableCell>
                      {doOdczytu ? (
                        <span className="text-xs">{pokazWartosc(kod, wartosc)}</span>
                      ) : (
                        <Input
                          aria-label={opis.nazwa}
                          className={cn("h-8 bg-card text-xs", zmieniona && "border-ostrzezenie")}
                          placeholder="brak"
                          value={wpisane[kod] ?? (wartosc === null ? "" : zaokraglij(wartosc as number))}
                          onChange={(e) => setWpisane({ ...wpisane, [kod]: e.target.value })}
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      {percentyl === undefined || percentyl === null ? (
                        <span className="text-xs text-pomocniczy">{czyFlaga(kod) ? pokazWartosc(kod, wartosc) : ""}</span>
                      ) : (
                        <div className="flex flex-col gap-1">
                          <div className="relative h-1.5 bg-muted">
                            <div className="absolute inset-y-0 left-1/4 w-1/2 bg-linia-mocna" />
                            <div
                              className="absolute inset-y-0 w-0.75 bg-primary"
                              style={{ left: `${Math.min(percentyl, 99)}%` }}
                            />
                          </div>
                          <span className="text-xs text-muted-foreground">wyżej niż {percentyl}%</span>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>

      <CardFooter className="mt-auto items-center gap-2 border-t pt-4 pb-4">
        <span
          className={cn(
            "flex-1 text-xs",
            blad ? "text-spadek" : czekaNaPrzeliczenie && zmienione.length > 0 ? "text-ostrzezenie" : "text-muted-foreground"
          )}
        >
          {stopka}
        </span>
        <Button variant="outline" disabled={zmienione.length === 0 && przeliczona === null} onClick={przywroc}>
          Przywróć
        </Button>
        <Button disabled={!czekaNaPrzeliczenie || liczy} onClick={przelicz}>
          {liczy && <Spinner data-icon="inline-start" />}
          Przelicz
        </Button>
      </CardFooter>
    </Card>
  )
}

// W polu pokazujemy rozsądną liczbę miejsc po przecinku, z polskim przecinkiem.
function zaokraglij(wartosc: number) {
  const miejsca = Math.abs(wartosc) >= 100 || Number.isInteger(wartosc) ? 0 : Math.abs(wartosc) >= 1 ? 2 : 4
  return String(Number(wartosc.toFixed(miejsca))).replace(".", ",")
}
