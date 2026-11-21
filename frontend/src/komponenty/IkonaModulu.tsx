import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { TLO } from "@/lib/kolory"
import type { Kolor } from "@/typy"

export function IkonaModulu({ kolor, ikona: Ikona, tekst }: { kolor: Kolor; ikona?: LucideIcon; tekst?: string }) {
  let zawartosc = <span className="size-2 bg-white" />
  if (tekst) {
    zawartosc = <>{tekst}</>
  } else if (Ikona) {
    zawartosc = <Ikona className="size-3.5" strokeWidth={2.25} />
  }

  return (
    <span
      className={cn(
        "flex size-6 shrink-0 items-center justify-center rounded-sm text-xs font-semibold text-white",
        TLO[kolor]
      )}
    >
      {zawartosc}
    </span>
  )
}
