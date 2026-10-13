import { OPISY_CECH } from "@/dane/opisyCech"
import type { DaneDzialki, WynikWyceny } from "@/typy"

// Raport wyceny jako CSV dla Excela: średnik między kolumnami, przecinek dziesiętny,
// znacznik BOM, żeby polskie znaki otworzyły się poprawnie.

function komorka(wartosc: string | number | null | undefined) {
  if (wartosc === null || wartosc === undefined) {
    return ""
  }
  let tekst = typeof wartosc === "number" ? String(Math.round(wartosc * 10000) / 10000).replace(".", ",") : wartosc
  if (/[;"\n]/.test(tekst)) {
    tekst = `"${tekst.replaceAll('"', '""')}"`
  }
  return tekst
}

// Kwoty do groszy. Wartości cech zostają z czterema miejscami po przecinku.
function grosze(wartosc: number) {
  return Math.round(wartosc * 100) / 100
}

export function raportCsv(dzialka: DaneDzialki, wynik: WynikWyceny) {
  const { wycena } = wynik
  const powierzchnia = Number(dzialka.powierzchnia.replace(",", "."))
  const glowne = wynik.wyjasnienia.find((w) => w.model === wycena.model)
  const wklady = new Map(glowne?.wklady.map((w) => [w.kod, w.wklad]) ?? [])

  const wiersze: (string | number | null)[][] = [
    ["Działka", dzialka.identyfikator],
    ["Gmina", dzialka.gmina],
    ["Powiat", dzialka.powiat],
    ["Województwo", dzialka.wojewodztwo],
    ["Powierzchnia [m²]", powierzchnia],
    ["Data wyceny", dzialka.dataWyceny],
    ["Model", wycena.model],
    ["Cena [zł/m²]", grosze(wycena.cenaM2)],
    ["Wartość [zł]", Math.round(wycena.cenaM2 * powierzchnia)],
    ["Przedział 80% od [zł/m²]", grosze(wycena.przedzialOd)],
    ["Przedział 80% do [zł/m²]", grosze(wycena.przedzialDo)],
    ["Pewność", wycena.pewnosc],
    [],
    ["Model", "Cena [zł/m²]", "MAE na teście", "R² na teście"],
    ...wynik.modele.map((m) => [m.nazwa, grosze(m.cenaM2), grosze(m.mae), m.r2]),
    [],
    ["Kod cechy", "Cecha", "Wartość", `Wkład w wycenę ${wycena.model} [zł/m²]`],
    ...OPISY_CECH.map((opis) => [opis.kod, opis.nazwa, wynik.cechy[opis.kod] ?? null, grosze(wklady.get(opis.kod) ?? 0)]),
  ]
  return "\uFEFF" + wiersze.map((w) => w.map(komorka).join(";")).join("\r\n")
}

export function pobierzRaport(dzialka: DaneDzialki, wynik: WynikWyceny) {
  const plik = new Blob([raportCsv(dzialka, wynik)], { type: "text/csv;charset=utf-8" })
  const adres = URL.createObjectURL(plik)
  const link = document.createElement("a")
  link.href = adres
  link.download = `wycena_${dzialka.identyfikator.replaceAll("/", "-")}_${dzialka.dataWyceny}.csv`
  link.click()
  // Adres zwalniamy chwilę później: część przeglądarek zaczyna pobieranie dopiero po kliknięciu.
  setTimeout(() => URL.revokeObjectURL(adres), 1000)
}
