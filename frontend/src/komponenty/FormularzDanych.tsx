import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSeparator,
  FieldSet,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { cn } from "@/lib/utils"
import { TLO } from "@/lib/kolory"
import { liczba } from "@/lib/format"
import {
  PRAWA,
  PRZEZNACZENIA,
  RODZAJE_GRUNTU,
  SPRZEDAJACY,
  nazwaOpcji,
  nazwaPrzeznaczenia,
} from "@/dane/slowniki"
import type { DaneDzialki, Kolor, Podpowiedz } from "@/typy"

// Grupy cech, które backend liczy sam po kliknięciu „Wyceń”. Z formularza pochodzi
// pozostałe 30: powierzchnia, rodzaj gruntu, prawo, sprzedający i 26 flag przeznaczenia.
const AUTOMATYCZNE: { kolor: Kolor; nazwa: string }[] = [
  { kolor: "sukces", nazwa: "Lokalizacja 5" },
  { kolor: "ostrzezenie", nazwa: "Otoczenie OSM 27" },
  { kolor: "rynek", nazwa: "Sąsiedztwo cenowe 8" },
  { kolor: "akcja", nazwa: "Geometria 2" },
  { kolor: "model", nazwa: "Czas 2" },
]

const OPCJE_RODZAJU = RODZAJE_GRUNTU.map((r) => ({ label: r.nazwa, value: r.kod }))

const OPCJE_PRZEZNACZENIA = PRZEZNACZENIA.flatMap((g) =>
  g.opcje.map((o) => ({ label: o.nazwa, value: o.kod }))
)

type Props = {
  dzialka: DaneDzialki | null
  podpowiedz: Podpowiedz | null
  onZmien: (dzialka: DaneDzialki) => void
  onWycen: () => void
}

export function FormularzDanych({ dzialka, podpowiedz, onZmien, onWycen }: Props) {
  if (!dzialka) {
    return (
      <Card className="w-[500px] shrink-0">
        <CardHeader>
          <CardTitle>Dane do wyceny</CardTitle>
          <CardDescription>
            Kliknij działkę na mapie albo wyszukaj ją po numerze. Dane z ewidencji uzupełnią
            się same.
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  function zmien(pole: keyof DaneDzialki, wartosc: string) {
    onZmien({ ...dzialka!, [pole]: wartosc })
  }

  // Bez tych pięciu informacji wycena nie ma sensu.
  const powierzchnia = Number(dzialka.powierzchnia.replace(",", "."))
  const wymagane = [
    { nazwa: "powierzchnia", gotowe: powierzchnia > 0 },
    { nazwa: "rodzaj gruntu", gotowe: dzialka.rodzajGruntu !== "" },
    { nazwa: "przeznaczenie", gotowe: dzialka.przeznaczenie !== "" },
    { nazwa: "prawo", gotowe: dzialka.prawo !== "" },
    { nazwa: "sprzedający", gotowe: dzialka.sprzedajacy !== "" },
  ]
  const brakujace = wymagane.filter((p) => !p.gotowe).map((p) => p.nazwa)
  const uzupelnione = wymagane.length - brakujace.length
  const komplet = brakujace.length === 0
  const pokazPodpowiedz = podpowiedz !== null && dzialka.przeznaczenie !== podpowiedz.przeznaczenie
  const pokazRodzaj = podpowiedz?.rodzajGruntu && dzialka.rodzajGruntu !== podpowiedz.rodzajGruntu.kod
  const miejscePodpowiedzi = podpowiedz?.obszar === "gmina" ? `gminie ${dzialka.gmina}` : `obrębie ${dzialka.obreb}`
  const narysowana = dzialka.zrodloGranicy === "rysunek"

  const wiersze = [
    ["Identyfikator", narysowana ? "—" : dzialka.identyfikator],
    ["Obręb", `${dzialka.obreb} (${dzialka.terytObrebu})`],
    ["Gmina", dzialka.gmina],
    ["Powiat", dzialka.powiat],
    ["Pole z granicy", `${liczba(dzialka.pole)} m²`],
    ["Wskaźnik zwartości", liczba(dzialka.zwartosc, 2)],
  ]

  return (
    <Card className="w-[500px] shrink-0">
      <CardHeader>
        <CardTitle>Dane do wyceny</CardTitle>
        <CardDescription>
          {narysowana ? `Granica narysowana w obrębie ${dzialka.obreb}` : `Działka ${dzialka.identyfikator}`}
        </CardDescription>
      </CardHeader>

      <CardContent>
        <FieldGroup>
          <FieldSet>
            <FieldLegend>2. Dane z ewidencji</FieldLegend>
            <FieldDescription>
              {narysowana
                ? "Granica narysowana ręcznie. Obręb i gminę pobrano z ewidencji, pole policzono z rysunku."
                : "Granica i dane z ewidencji (ULDK). Sprawdź powierzchnię i wybierz rodzaj gruntu."}
            </FieldDescription>

            <Table className="border">
              <TableBody>
                {wiersze.map(([nazwa, wartosc]) => (
                  <TableRow key={nazwa}>
                    <TableCell className="text-muted-foreground">{nazwa}</TableCell>
                    <TableCell className="text-right font-mono">{wartosc}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            <div className="grid grid-cols-2 gap-3">
              <Field data-invalid={powierzchnia > 0 ? undefined : true}>
                <FieldLabel htmlFor="powierzchnia">
                  Powierzchnia [m²] <span className="text-spadek">*</span>
                  <Badge variant={narysowana ? "ostrzezenie" : "akcja"} className="ml-auto font-mono">
                    {narysowana ? "z rysunku" : "z ULDK"}
                  </Badge>
                </FieldLabel>
                <Input
                  id="powierzchnia"
                  inputMode="decimal"
                  className="font-mono"
                  value={dzialka.powierzchnia}
                  onChange={(e) => zmien("powierzchnia", e.target.value)}
                  aria-invalid={powierzchnia > 0 ? undefined : true}
                />
              </Field>

              <Field>
                <FieldLabel>
                  Rodzaj gruntu <span className="text-spadek">*</span>
                </FieldLabel>
                <Select
                  items={OPCJE_RODZAJU}
                  value={dzialka.rodzajGruntu || null}
                  onValueChange={(v) => zmien("rodzajGruntu", v ? String(v) : "")}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Wybierz…" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {OPCJE_RODZAJU.map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
            </div>

            {pokazRodzaj && podpowiedz?.rodzajGruntu && (
              <Alert variant="podpowiedz">
                <AlertTitle className="text-xs font-normal text-muted-foreground">
                  Najczęstszy rodzaj gruntu wśród sprzedaży w {miejscePodpowiedzi}
                </AlertTitle>
                <AlertDescription className="font-medium text-foreground">
                  {nazwaOpcji(RODZAJE_GRUNTU, podpowiedz.rodzajGruntu.kod)} · {podpowiedz.rodzajGruntu.udzial}%
                </AlertDescription>
                <AlertAction className="top-1/2 -translate-y-1/2">
                  <Button
                    size="sm"
                    variant="akcja"
                    onClick={() => zmien("rodzajGruntu", podpowiedz.rodzajGruntu!.kod)}
                  >
                    Użyj
                  </Button>
                </AlertAction>
              </Alert>
            )}
          </FieldSet>

          <FieldSeparator />

          <FieldSet>
            <FieldLegend>3. Dane do uzupełnienia</FieldLegend>
            <FieldDescription>
              Tych informacji nie ma w żadnym rejestrze, a model z nich korzysta.
            </FieldDescription>

            <Field>
              <FieldLabel>
                Przeznaczenie w planie miejscowym lub WZ <span className="text-spadek">*</span>
              </FieldLabel>
              <Select
                items={OPCJE_PRZEZNACZENIA}
                value={dzialka.przeznaczenie || null}
                onValueChange={(v) => zmien("przeznaczenie", v ? String(v) : "")}
              >
                <SelectTrigger className={cn("w-full", !dzialka.przeznaczenie && "border-akcja")}>
                  <SelectValue placeholder="Wybierz przeznaczenie…" />
                </SelectTrigger>
                <SelectContent alignItemWithTrigger={false}>
                  {PRZEZNACZENIA.map((grupa) => (
                    <SelectGroup key={grupa.grupa}>
                      <SelectLabel>{grupa.grupa}</SelectLabel>
                      {grupa.opcje.map((o) => (
                        <SelectItem key={o.kod} value={o.kod}>
                          {o.nazwa}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  ))}
                </SelectContent>
              </Select>

              {pokazPodpowiedz && (
                <Alert variant="podpowiedz">
                  <AlertTitle className="text-xs font-normal text-muted-foreground">
                    Podpowiedź z transakcji w {miejscePodpowiedzi}
                  </AlertTitle>
                  <AlertDescription className="font-medium text-foreground">
                    {nazwaPrzeznaczenia(podpowiedz.przeznaczenie)} · {podpowiedz.udzial}% z{" "}
                    {podpowiedz.liczbaSprzedazy} sprzedaży z wpisem
                  </AlertDescription>
                  <AlertAction className="top-1/2 -translate-y-1/2">
                    <Button
                      size="sm"
                      variant="akcja"
                      onClick={() => zmien("przeznaczenie", podpowiedz.przeznaczenie)}
                    >
                      Użyj
                    </Button>
                  </AlertAction>
                </Alert>
              )}
            </Field>

            <Field>
              <FieldLabel>
                Prawo do gruntu <span className="text-spadek">*</span>
              </FieldLabel>
              <ToggleGroup
                variant="wybor"
                spacing={0}
                className="w-full"
                value={[dzialka.prawo]}
                onValueChange={(v) => v.length > 0 && zmien("prawo", String(v[0]))}
              >
                {PRAWA.map((p) => (
                  <ToggleGroupItem key={p.kod} value={p.kod} className="flex-1">
                    {p.nazwa}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </Field>

            <Field>
              <FieldLabel>
                Kto sprzedaje <span className="text-spadek">*</span>
              </FieldLabel>
              <ToggleGroup
                variant="wybor"
                spacing={0}
                className="w-full"
                value={[dzialka.sprzedajacy]}
                onValueChange={(v) => v.length > 0 && zmien("sprzedajacy", String(v[0]))}
              >
                {SPRZEDAJACY.map((s) => (
                  <ToggleGroupItem key={s.kod} value={s.kod} className="flex-1">
                    {s.nazwa}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </Field>

            <Field>
              <FieldLabel htmlFor="data">Data wyceny</FieldLabel>
              <Input
                id="data"
                type="date"
                className="font-mono"
                value={dzialka.dataWyceny}
                onChange={(e) => zmien("dataWyceny", e.target.value)}
              />
            </Field>
          </FieldSet>
        </FieldGroup>
      </CardContent>

      <CardFooter className="flex-col items-stretch gap-3 border-t pt-4">
        <div className="flex items-center justify-between text-xs">
          <span>
            Wymagane pola: {uzupelnione} z {wymagane.length}
          </span>
          {!komplet && <span className="text-spadek">brakuje: {brakujace.join(", ")}</span>}
        </div>
        <Progress value={(uzupelnione / wymagane.length) * 100} />

        <Button size="lg" disabled={!komplet} onClick={onWycen}>
          Wyceń działkę
        </Button>

        <div className="flex flex-col gap-2 pb-4">
          <span className="text-xs text-muted-foreground">
            Resztę z 74 cech program policzy sam po kliknięciu „Wyceń”:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {AUTOMATYCZNE.map((g) => (
              <Badge key={g.nazwa} variant="outline">
                <span className={cn("size-2", TLO[g.kolor])} />
                {g.nazwa}
              </Badge>
            ))}
          </div>
        </div>
      </CardFooter>
    </Card>
  )
}
