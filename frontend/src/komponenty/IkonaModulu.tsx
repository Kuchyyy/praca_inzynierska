import { cn } from "@/lib/utils"
import { TLO } from "@/lib/kolory"
import type { Kolor } from "@/typy"

// Kolorowy kwadrat przy tytule modułu, jak w Figmie.
export function IkonaModulu({ kolor, tekst }: { kolor: Kolor; tekst?: string }) {
  return (
    <span
      className={cn(
        "flex size-6 shrink-0 items-center justify-center rounded-sm font-mono text-xs font-medium text-white",
        TLO[kolor]
      )}
    >
      {tekst ?? <span className="size-2 bg-white" />}
    </span>
  )
}
