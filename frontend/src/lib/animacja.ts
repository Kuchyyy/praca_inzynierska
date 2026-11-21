import { useEffect, useRef, useState } from "react"

export function ograniczonyRuch() {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches
  } catch {
    return false
  }
}

export function useLicznik(cel: number, czasMs = 800, start = cel) {
  const [wartosc, setWartosc] = useState(start)
  const biezaca = useRef(start)

  useEffect(() => {
    const od = biezaca.current
    const poczatek = performance.now()
    let klatka = 0

    function krok(teraz: number) {
      const t = Math.min((teraz - poczatek) / czasMs, 1)
      const postep = 1 - Math.pow(1 - t, 3)
      biezaca.current = od + (cel - od) * postep
      setWartosc(biezaca.current)
      if (t < 1) {
        klatka = requestAnimationFrame(krok)
      }
    }

    klatka = requestAnimationFrame(krok)
    return () => cancelAnimationFrame(klatka)
  }, [cel, czasMs])

  return ograniczonyRuch() ? cel : wartosc
}
