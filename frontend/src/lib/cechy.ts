import { opisCechy } from "@/dane/opisyCech"
import { PRAWA, RODZAJE_GRUNTU, SPRZEDAJACY, nazwaOpcji } from "@/dane/slowniki"
import type { WartoscCechy } from "@/typy"
import { wartoscCechy } from "./format"

const SLOWNIKI: Record<string, { kod: string; nazwa: string }[]> = {
  tran_sprzedajacy: SPRZEDAJACY,
  nier_prawo: PRAWA,
  dzi_sposob_uzyt: RODZAJE_GRUNTU,
}

export function czyFlaga(kod: string) {
  return kod.startsWith("przezn_") || kod.startsWith("czy_") || kod === "ma_wpis_przeznaczenia"
}

export function pokazWartosc(kod: string, wartosc: WartoscCechy) {
  if (wartosc === null || wartosc === undefined) {
    return "brak"
  }
  if (typeof wartosc === "string") {
    return kod in SLOWNIKI ? nazwaOpcji(SLOWNIKI[kod], wartosc) : wartosc
  }
  if (czyFlaga(kod)) {
    return wartosc === 1 ? "tak" : "nie"
  }
  if (kod === "x_2180" || kod === "y_2180" || kod === "rok") {
    return String(Math.round(wartosc))
  }
  const opis = opisCechy(kod)
  const zaokraglona = Number.isInteger(wartosc) ? wartosc : Number(wartosc.toFixed(2))
  return wartoscCechy(zaokraglona, opis.jednostka)
}
