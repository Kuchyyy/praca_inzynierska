import { ArrowLeftIcon, BookOpenIcon, DownloadIcon, HistoryIcon, LandPlotIcon, Trash2Icon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { data, kwota, zaM2 } from "@/lib/format"
import type { WpisHistorii } from "@/lib/historia"
import type { DaneDzialki, Etap, Widok } from "@/typy"

type Props = {
  etap: Etap
  widok: Widok
  dzialka: DaneDzialki | null
  historia: WpisHistorii[]
  onAnuluj: () => void
  onPonownie: () => void
  onEksportuj: () => void
  onOtworz: (wpis: WpisHistorii) => void
  onWyczyscHistorie: () => void
  onCechy: () => void
  onWroc: () => void
}

export function Naglowek(props: Props) {
  const { etap, widok, dzialka, onAnuluj, onPonownie, onEksportuj, onCechy, onWroc } = props

  let okruszek = etap === "dane" || !dzialka ? "Nowa wycena" : `Działka ${dzialka.identyfikator} · ${dzialka.gmina}`
  if (widok === "cechy") {
    okruszek = "Opis cech modelu"
  }

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-card px-5">
      <span className="flex size-7 items-center justify-center rounded-sm bg-akcja text-white">
        <LandPlotIcon className="size-4" />
      </span>
      <span className="text-sm font-semibold">Wycena działek</span>
      <span className="text-sm text-linia-mocna">/</span>
      <span className="flex-1 truncate text-sm text-muted-foreground">{okruszek}</span>

      {widok === "cechy" ? (
        <Button onClick={onWroc}>
          <ArrowLeftIcon data-icon="inline-start" />
          Wróć do wyceny
        </Button>
      ) : (
        <>
          {etap !== "liczenie" && <HistoriaWycen {...props} />}
          {etap === "liczenie" && (
            <Button variant="outline" onClick={onAnuluj}>
              Anuluj
            </Button>
          )}
          {etap === "wynik" && (
            <>
              <Button variant="outline" onClick={onEksportuj}>
                <DownloadIcon data-icon="inline-start" />
                Eksportuj CSV
              </Button>
              <Button onClick={onPonownie}>Wyceń ponownie</Button>
            </>
          )}
          <Button variant="outline" onClick={onCechy}>
            <BookOpenIcon data-icon="inline-start" />
            Cechy
          </Button>
        </>
      )}
    </header>
  )
}

// Ostatnie wyceny z tej przeglądarki. Kliknięcie wycenia działkę jeszcze raz z tymi samymi danymi.
function HistoriaWycen({ historia, onOtworz, onWyczyscHistorie }: Props) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="outline" />}>
        <HistoryIcon data-icon="inline-start" />
        Historia wycen
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-96">
        <DropdownMenuGroup>
          <DropdownMenuLabel>Ostatnie wyceny w tej przeglądarce</DropdownMenuLabel>
          {historia.length === 0 && (
            <DropdownMenuItem disabled>Brak zapisanych wycen. Pojawią się tu po pierwszej wycenie.</DropdownMenuItem>
          )}
          {historia.map((wpis) => (
            <DropdownMenuItem key={wpis.dzialka.identyfikator} onClick={() => onOtworz(wpis)} className="items-start gap-3 py-2">
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="truncate font-medium">{wpis.dzialka.identyfikator}</span>
                <span className="truncate text-xs text-muted-foreground">
                  {wpis.dzialka.gmina} · wycena na {data(wpis.dzialka.dataWyceny)}
                </span>
              </div>
              <div className="flex flex-col items-end">
                <span className="font-medium">{kwota(wpis.wartosc)}</span>
                <span className="text-xs text-muted-foreground">{zaM2(wpis.cenaM2)}</span>
              </div>
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
        {historia.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onClick={onWyczyscHistorie}>
              <Trash2Icon />
              Wyczyść historię
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
