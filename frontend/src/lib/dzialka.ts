import type { DaneDzialki, Granica } from "@/typy"
import { naMetry, obwod, pole, srodek, zwartosc } from "./geometria"
import type { DzialkaUldk, ObrebUldk } from "./uldk"

function poleFormularza() {
  return {
    rodzajGruntu: "",
    przeznaczenie: "",
    prawo: "wlasnoscNieruchomosciGruntowej",
    sprzedajacy: "osobaFizyczna",
    dataWyceny: new Date().toISOString().slice(0, 10),
  }
}

export function zUldk(dzialka: DzialkaUldk): DaneDzialki {
  const polePowierzchni = Math.round(dzialka.pole)
  return {
    identyfikator: dzialka.identyfikator,
    zrodloGranicy: "uldk",
    numer: dzialka.numer,
    obreb: dzialka.obreb,
    terytObrebu: dzialka.identyfikator.split(".").slice(0, 2).join("."),
    gmina: dzialka.gmina,
    powiat: dzialka.powiat,
    wojewodztwo: dzialka.wojewodztwo,
    granica: dzialka.granica,
    srodek: srodek(dzialka.granica),
    pole: dzialka.pole,
    zwartosc: zwartosc(dzialka.pole, dzialka.obwod),
    powierzchnia: String(polePowierzchni),
    ...poleFormularza(),
  }
}

export function zRysunku(granica: Granica, obreb: ObrebUldk): DaneDzialki {
  const srodekGranicy = srodek(granica)
  const wMetrach = naMetry(granica, srodekGranicy)
  const poleM2 = pole(wMetrach)
  return {
    identyfikator: `${obreb.teryt} · granica narysowana`,
    zrodloGranicy: "rysunek",
    numer: "",
    obreb: obreb.obreb,
    terytObrebu: obreb.teryt,
    gmina: obreb.gmina,
    powiat: obreb.powiat,
    wojewodztwo: obreb.wojewodztwo,
    granica,
    srodek: srodekGranicy,
    pole: poleM2,
    zwartosc: zwartosc(poleM2, obwod(wMetrach)),
    powierzchnia: String(Math.round(poleM2)),
    ...poleFormularza(),
  }
}
