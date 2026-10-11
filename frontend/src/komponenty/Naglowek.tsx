import { ArrowLeftIcon, BookOpenIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { DaneDzialki, Etap, Widok } from "@/typy"

type Props = {
  etap: Etap
  widok: Widok
  dzialka: DaneDzialki | null
  onAnuluj: () => void
  onPonownie: () => void
  onCechy: () => void
  onWroc: () => void
}

export function Naglowek({ etap, widok, dzialka, onAnuluj, onPonownie, onCechy, onWroc }: Props) {
  let okruszek = etap === "dane" || !dzialka ? "Nowa wycena" : `Działka ${dzialka.identyfikator} · ${dzialka.gmina}`
  if (widok === "cechy") {
    okruszek = "Opis cech modelu"
  }

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-card px-5">
      <span className="size-5.5 rounded-sm bg-primary" />
      <span className="text-sm font-medium">Wycena działek</span>
      <span className="text-sm text-pomocniczy">/</span>
      <span className="flex-1 truncate text-sm text-muted-foreground">{okruszek}</span>

      {widok === "cechy" ? (
        <Button onClick={onWroc}>
          <ArrowLeftIcon data-icon="inline-start" />
          Wróć do wyceny
        </Button>
      ) : (
        <>
          {etap === "dane" && <Button variant="outline">Historia wycen</Button>}
          {etap === "liczenie" && (
            <Button variant="outline" onClick={onAnuluj}>
              Anuluj
            </Button>
          )}
          {etap === "wynik" && (
            <>
              <Button variant="outline">Eksportuj</Button>
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
