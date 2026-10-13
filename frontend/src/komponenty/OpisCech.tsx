import { useEffect, useMemo, useState } from "react"
import { BookOpenIcon, SearchIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { KOLOR_GRUPY, TLO } from "@/lib/kolory"
import { data, liczba, zaM2, zeZnakiem } from "@/lib/format"
import { czyFlaga, pokazWartosc } from "@/lib/cechy"
import { KROKI } from "@/dane/kroki"
import { OPISY_CECH, ROZDZIALY } from "@/dane/opisyCech"
import type { OpisCechy, OpisModelu, WynikWyceny } from "@/typy"
import { IkonaModulu } from "./IkonaModulu"

const ROZDZIALY_OGOLNE = [
  { kod: "kroki", nazwa: "Kroki wyceny" },
  { kod: "trening", nazwa: "Trening modeli" },
  { kod: "wplyw", nazwa: "Wpływ cech na wycenę" },
  { kod: "przeciek", nazwa: "Ochrona przed przeciekiem ceny" },
]

type Props = {
  model: OpisModelu | null
  wynik: WynikWyceny | null
  // Cecha, do której przewijamy po otwarciu, np. po kliknięciu ⓘ w tabeli cech.
  cel: string | null
}

function przewin(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })
}

export function OpisCech({ model, wynik, cel }: Props) {
  const [szukane, setSzukane] = useState("")

  useEffect(() => {
    if (cel) {
      document.getElementById(`cecha-${cel}`)?.scrollIntoView({ block: "start" })
    } else {
      window.scrollTo({ top: 0 })
    }
  }, [cel])

  // Miejsce każdej cechy w rankingu ważności, osobno dla każdego modelu.
  const miejsca = useMemo(() => {
    const wynikMiejsc: Record<string, Record<string, number>> = {}
    if (!model) {
      return wynikMiejsc
    }
    for (const [nazwa, waznosci] of Object.entries(model.waznosc)) {
      const kolejnosc = Object.keys(waznosci).sort((a, b) => waznosci[b] - waznosci[a])
      wynikMiejsc[nazwa] = {}
      kolejnosc.forEach((kod, i) => (wynikMiejsc[nazwa][kod] = i + 1))
    }
    return wynikMiejsc
  }, [model])

  const fraza = szukane.trim().toLowerCase()
  const pasujace = OPISY_CECH.filter((o) => !fraza || o.nazwa.toLowerCase().includes(fraza) || o.kod.includes(fraza))

  return (
    <div className="grid grid-cols-[300px_1fr] items-start gap-4">
      <Card className="sticky top-19 max-h-[calc(100svh-6rem)]">
        <CardHeader>
          <CardTitle>Spis treści</CardTitle>
          <CardDescription>{OPISY_CECH.length} cech modelu w {ROZDZIALY.length} rozdziałach</CardDescription>
        </CardHeader>
        <CardContent className="flex min-h-0 flex-col gap-3">
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={szukane} onChange={(e) => setSzukane(e.target.value)} placeholder="Szukaj cechy…" className="pl-8" />
          </div>

          <div className="flex min-h-0 flex-col gap-3 overflow-y-auto pb-4">
            {!fraza && (
              <div className="flex flex-col">
                <span className="px-2 pb-1 text-xs text-pomocniczy">Jak to działa</span>
                {ROZDZIALY_OGOLNE.map((r) => (
                  <PozycjaSpisu key={r.kod} onClick={() => przewin(`rozdzial-${r.kod}`)}>
                    {r.nazwa}
                  </PozycjaSpisu>
                ))}
              </div>
            )}
            {ROZDZIALY.map((rozdzial) => {
              const cechy = pasujace.filter((o) => o.rozdzial === rozdzial.kod)
              if (cechy.length === 0) {
                return null
              }
              return (
                <div key={rozdzial.kod} className="flex flex-col">
                  <span className="px-2 pb-1 text-xs text-pomocniczy">
                    {rozdzial.nazwa} · {cechy.length}
                  </span>
                  {cechy.map((o) => (
                    <PozycjaSpisu key={o.kod} onClick={() => przewin(`cecha-${o.kod}`)}>
                      <span className={cn("size-1.5 shrink-0", TLO[KOLOR_GRUPY[o.grupa]])} />
                      <span className="truncate">{o.nazwa}</span>
                    </PozycjaSpisu>
                  ))}
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      <div className="flex min-w-0 flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2.5 text-xl">
              <IkonaModulu kolor="akcja" ikona={BookOpenIcon} />
              Opis cech modelu
            </CardTitle>
            <CardDescription className="pl-8.5">
              Co oznacza każda cecha, jak jest liczona i gdzie powstaje w kodzie.
              {wynik && " Przy każdej cesze widać też jej wartość i wkład dla ostatnio wycenianej działki."}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-8">
            <RozdzialyOgolne model={model} />
          </CardContent>
        </Card>

        {ROZDZIALY.map((rozdzial) => (
          <Card key={rozdzial.kod} id={`rozdzial-${rozdzial.kod}`} className="scroll-mt-19">
            <CardHeader>
              <CardTitle className="text-lg">{rozdzial.nazwa}</CardTitle>
              <CardDescription>{rozdzial.opis}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col">
              {OPISY_CECH.filter((o) => o.rozdzial === rozdzial.kod).map((opis) => (
                <SekcjaCechy key={opis.kod} opis={opis} model={model} miejsca={miejsca} wynik={wynik} />
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function PozycjaSpisu({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2 rounded-xs px-2 py-1 text-left text-sm hover:bg-muted"
    >
      {children}
    </button>
  )
}

function Etykieta({ children }: { children: React.ReactNode }) {
  return <span className="text-xs font-medium tracking-wide text-pomocniczy uppercase">{children}</span>
}

function RozdzialyOgolne({ model }: { model: OpisModelu | null }) {
  return (
    <>
      <section id="rozdzial-kroki" className="flex scroll-mt-19 flex-col gap-3">
        <h2 className="text-lg font-semibold">Kroki wyceny</h2>
        <p className="text-sm">
          Serwer wyceny (backend/api.py) liczy dla wskazanej działki te same cechy co przygotowanie danych do treningu,
          w sześciu krokach.
        </p>
        <ol className="flex flex-col gap-2">
          {KROKI.map((k) => (
            <li key={k.numer} className="flex gap-3 text-sm">
              <IkonaModulu kolor={k.kolor} tekst={String(k.numer)} />
              <div className="flex flex-col">
                <span className="font-medium">
                  {k.nazwa} · <span className="font-normal text-muted-foreground">{k.opis}</span>
                </span>
                <span className="text-muted-foreground">{k.podkroki.join(" · ")}</span>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section id="rozdzial-trening" className="flex scroll-mt-19 flex-col gap-3">
        <h2 className="text-lg font-semibold">Trening modeli</h2>
        {model ? (
          <>
            <p className="text-sm">
              Modele uczą się na {liczba(model.uczenie.wiersze)} sprzedażach sprzed {data(model.uczenie.przed)}, a sprawdzane są na{" "}
              {liczba(model.test.wiersze)} sprzedażach od {data(model.test.od)}. Ceny za m² spoza przedziału{" "}
              {zaM2(model.progiCeny.dol)} – {zaM2(model.progiCeny.gora)} odrzucono jako błędy rejestru. Progi policzono
              tylko na treningu i tak samo zastosowano do testu (odrzucono {liczba(model.test.odrzucone)} sprzedaży testowych).
              Powiat i gmina są zamieniane na średnią ceny z treningu, pozostałe kategorie na kolumny 0/1, a braki liczb na
              medianę z osobną kolumną „brak”.
            </p>
            <Table className="border">
              <TableHeader>
                <TableRow>
                  <TableHead>Model</TableHead>
                  <TableHead>Uczy się na</TableHead>
                  <TableHead className="text-right">MAE</TableHead>
                  <TableHead className="text-right">RMSE</TableHead>
                  <TableHead className="text-right">R²</TableHead>
                  <TableHead className="text-right">Mediana błędu</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {model.modele.map((m) => (
                  <TableRow key={m.nazwa}>
                    <TableCell className={cn(m.nazwa === model.najlepszy && "font-medium")}>
                      {m.nazwa}
                      {m.nazwa === model.najlepszy && (
                        <Badge variant="model" className="ml-2">
                          wynik główny
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{m.na_logarytmie ? "logarytmie ceny" : "cenie wprost"}</TableCell>
                    <TableCell className="text-right">{liczba(m.mae, 1)}</TableCell>
                    <TableCell className="text-right">{liczba(m.rmse, 1)}</TableCell>
                    <TableCell className="text-right">{liczba(m.r2, 3)}</TableCell>
                    <TableCell className="text-right">{liczba(m.mediana_bledu_procent, 1)}%</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="text-xs text-muted-foreground">
              MAE i RMSE w zł/m² na zbiorze testowym. Mediana błędu to typowe odchylenie wyceny od ceny z aktu, w procentach.
            </p>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Metryki pojawią się, gdy działa serwer wyceny.</p>
        )}
      </section>

      <section id="rozdzial-wplyw" className="flex scroll-mt-19 flex-col gap-3">
        <h2 className="text-lg font-semibold">Wpływ cech na wycenę</h2>
        <p className="text-sm">
          Dla każdej wyceny i każdego modelu wycena rozkłada się na punkt startowy i wkłady cech w zł/m². Punkt startowy
          to przeciętna wycena modelu dla działek z treningu, a suma wkładów daje dokładnie cenę modelu.
        </p>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
          <li>
            Regresja liniowa i bayesowska: wkład cechy to jej współczynnik razy odchylenie od średniej z treningu. Modele
            liczą na logarytmie ceny, więc wkłady są przeliczane na zł/m² tak, żeby dalej sumowały się do wyceny.
          </li>
          <li>
            Drzewo decyzyjne, las losowy i gradient boosting: wartości SHAP. Każde drzewo dzieli działki pytaniami o cechy,
            a SHAP sprawiedliwie rozdziela zmianę wyceny między cechy, uśredniając po wszystkich kolejnościach pytań.
          </li>
        </ul>
        <p className="text-sm">
          Ważność globalna to ważność permutacyjna: o ile złotych na m² rośnie błąd MAE na próbce testu, gdy wartości
          jednej cechy się przetasuje. Ta sama metoda dla każdego modelu, więc rankingi da się porównywać.
        </p>
      </section>

      <section id="rozdzial-przeciek" className="flex scroll-mt-19 flex-col gap-3">
        <h2 className="text-lg font-semibold">Ochrona przed przeciekiem ceny</h2>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
          <li>Cechy sąsiedztwa korzystają tylko ze sprzedaży ze ściśle wcześniejszego dnia niż wyceniana transakcja.</li>
          <li>Wcześniejsze sprzedaże tej samej działki nie są sąsiadami.</li>
          <li>W treningu referencjami są tylko transakcje treningowe; ceny testowe nigdy nie trafiają do cech.</li>
          <li>Wybór modeli i ich ustawień zapadł na walidacji z 2024 roku. Test zostaje na końcowy pomiar.</li>
          <li>
            Ograniczenie: OSM opisuje stan z 2026 roku, więc przy starszych sprzedażach część działek jest już zabudowana.
            To częściowy przeciek z przyszłości, głównie w cechach zabudowy.
          </li>
        </ul>
      </section>
    </>
  )
}

type PropsSekcji = {
  opis: OpisCechy
  model: OpisModelu | null
  miejsca: Record<string, Record<string, number>>
  wynik: WynikWyceny | null
}

function SekcjaCechy({ opis, model, miejsca, wynik }: PropsSekcji) {
  const statystyka = model?.statystyki[opis.kod]
  const najlepszy = model?.najlepszy ?? wynik?.wycena.model ?? ""
  const miejsceGlowne = miejsca[najlepszy]?.[opis.kod]

  return (
    <section id={`cecha-${opis.kod}`} className="flex scroll-mt-19 flex-col gap-4 border-t py-6 first:border-t-0 first:pt-0">
      <div className="flex items-start gap-3">
        <span className={cn("mt-1.5 size-3 shrink-0", TLO[KOLOR_GRUPY[opis.grupa]])} />
        <div className="flex flex-1 flex-col gap-0.5">
          <h3 className="text-base font-semibold">{opis.nazwa}</h3>
          <span className="font-mono text-xs text-muted-foreground">{opis.kod}</span>
        </div>
        {miejsceGlowne && (
          <Badge variant="outline">
            ważność #{miejsceGlowne} z {OPISY_CECH.length}
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_340px] gap-6">
        <div className="flex flex-col gap-4">
          <Akapit tytul="Co to jest">{opis.coTo}</Akapit>
          {opis.poCo && <Akapit tytul="Po co w modelu">{opis.poCo}</Akapit>}

          {opis.kroki.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <Etykieta>Jak liczona</Etykieta>
              <ol className="flex list-decimal flex-col gap-1 pl-5 text-sm">
                {opis.kroki.map((krok) => (
                  <li key={krok}>{krok}</li>
                ))}
              </ol>
            </div>
          )}

          {opis.wzor && (
            <div className="flex flex-col gap-1.5">
              <Etykieta>Wzór</Etykieta>
              <code className="rounded-xs bg-muted px-3 py-2 font-mono text-sm">{opis.wzor}</code>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Etykieta>W kodzie</Etykieta>
            <div className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-sm">
              <span className="text-muted-foreground">Trening (ETL)</span>
              <span className="font-mono text-xs leading-5">{opis.etl}</span>
              <span className="text-muted-foreground">Panel (wycena)</span>
              <span className="font-mono text-xs leading-5">{opis.panel}</span>
              <span className="text-muted-foreground">Źródło</span>
              <span>{opis.zrodlo}</span>
            </div>
          </div>

          {opis.uwagi && (
            <div className="flex flex-col gap-1 border-l-3 border-l-ostrzezenie bg-muted px-3 py-2">
              <Etykieta>Ograniczenia</Etykieta>
              <p className="text-sm">{opis.uwagi}</p>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-4">
          {wynik && <TaDzialka opis={opis} wynik={wynik} najlepszy={najlepszy} />}
          {statystyka && <Statystyki opis={opis} statystyka={statystyka} />}
          {model && <WaznoscWModelach kod={opis.kod} model={model} miejsca={miejsca} />}
        </div>
      </div>
    </section>
  )
}

function Akapit({ tytul, children }: { tytul: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <Etykieta>{tytul}</Etykieta>
      <p className="text-sm">{children}</p>
    </div>
  )
}

function TaDzialka({ opis, wynik, najlepszy }: { opis: OpisCechy; wynik: WynikWyceny; najlepszy: string }) {
  const wartosc = wynik.cechy[opis.kod]
  const percentyl = wynik.naTle.percentyle[opis.kod]
  const wyjasnienie = wynik.wyjasnienia.find((w) => w.model === najlepszy)
  const wklad = wyjasnienie?.wklady.find((w) => w.kod === opis.kod)?.wklad

  return (
    <div className="flex flex-col gap-2 rounded-xs border-2 border-akcja p-3">
      <Etykieta>Ta działka</Etykieta>
      <span className="text-lg font-medium">{pokazWartosc(opis.kod, wartosc ?? null)}</span>
      {percentyl !== undefined && percentyl !== null && (
        <span className="text-xs text-muted-foreground">
          wyżej niż {percentyl}% sprzedanych działek w {wynik.naTle.obszar === "gmina" ? "gminie" : "powiecie"}
        </span>
      )}
      {wklad !== undefined && (
        <span className={cn("text-xs font-medium", wklad >= 0 ? "text-sukces" : "text-spadek")}>
          Wkład w wycenę ({najlepszy}): {zeZnakiem(wklad)} zł/m²
        </span>
      )}
    </div>
  )
}

function Statystyki({ opis, statystyka }: { opis: OpisCechy; statystyka: NonNullable<OpisModelu["statystyki"][string]> }) {
  const kod = opis.kod

  if (statystyka.najczestsze) {
    return (
      <div className="flex flex-col gap-2">
        <Etykieta>Wartości w treningu</Etykieta>
        <Table className="border">
          <TableHeader>
            <TableRow>
              <TableHead>Najczęstsze</TableHead>
              <TableHead className="text-right">Sprzedaży</TableHead>
              <TableHead className="text-right">Mediana</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {statystyka.najczestsze.map((w) => (
              <TableRow key={w.wartosc}>
                <TableCell className="max-w-36 truncate">{pokazWartosc(kod, w.wartosc)}</TableCell>
                <TableCell className="text-right text-xs">{liczba(w.liczba)}</TableCell>
                <TableCell className="text-right text-xs">{zaM2(w.mediana_ceny)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <span className="text-xs text-muted-foreground">
          {liczba(statystyka.liczba_wartosci ?? 0)} różnych wartości · braki {liczba(statystyka.braki_procent, 1)}%
        </span>
      </div>
    )
  }

  if (czyFlaga(kod)) {
    return (
      <div className="flex flex-col gap-1">
        <Etykieta>Wartości w treningu</Etykieta>
        <span className="text-sm">
          1 w <span>{liczba((statystyka.srednia ?? 0) * 100, 2)}%</span> transakcji
        </span>
        {statystyka.spearman !== null && statystyka.spearman !== undefined && (
          <span className="text-xs text-muted-foreground">Korelacja z ceną (Spearman): {liczba(statystyka.spearman, 3)}</span>
        )}
      </div>
    )
  }

  const kwantyle: [string, number | null | undefined][] = [
    ["min", statystyka.min],
    ["p25", statystyka.p25],
    ["mediana", statystyka.mediana],
    ["p75", statystyka.p75],
    ["p99", statystyka.p99],
    ["max", statystyka.max],
  ]
  return (
    <div className="flex flex-col gap-2">
      <Etykieta>Wartości w treningu</Etykieta>
      <div className="grid grid-cols-3 gap-1.5">
        {kwantyle.map(([nazwa, wartosc]) => (
          <div key={nazwa} className="flex flex-col rounded-xs bg-muted px-2 py-1">
            <span className="text-xs text-muted-foreground">{nazwa}</span>
            <span className="truncate text-xs font-medium">
              {wartosc === null || wartosc === undefined ? "—" : pokazWartosc(kod, wartosc)}
            </span>
          </div>
        ))}
      </div>
      <span className="text-xs text-muted-foreground">
        Braki {liczba(statystyka.braki_procent, 1)}%
        {statystyka.zera_procent ? ` · zera ${liczba(statystyka.zera_procent, 1)}%` : ""}
        {statystyka.spearman !== null && statystyka.spearman !== undefined
          ? ` · korelacja z ceną (Spearman) ${liczba(statystyka.spearman, 3)}`
          : ""}
      </span>
    </div>
  )
}

function WaznoscWModelach({ kod, model, miejsca }: { kod: string; model: OpisModelu; miejsca: Record<string, Record<string, number>> }) {
  return (
    <div className="flex flex-col gap-2">
      <Etykieta>Ważność w modelach</Etykieta>
      <Table className="border">
        <TableBody>
          {model.modele.map((m) => {
            const wzrost = model.waznosc[m.nazwa]?.[kod] ?? 0
            return (
              <TableRow key={m.nazwa}>
                <TableCell className={cn("py-1.5", m.nazwa === model.najlepszy && "font-medium")}>{m.nazwa}</TableCell>
                <TableCell className="py-1.5 text-right text-xs">#{miejsca[m.nazwa]?.[kod] ?? "—"}</TableCell>
                <TableCell className="py-1.5 text-right text-xs">{zeZnakiem(wzrost)} zł/m²</TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      <span className="text-xs text-muted-foreground">Wzrost MAE po przetasowaniu cechy na próbce testu.</span>
    </div>
  )
}
