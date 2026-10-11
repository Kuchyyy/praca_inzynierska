import json
from collections import Counter

import pandas as pd


def zapisz_raport(katalog, liczniki, rozklad, opis):
    raport = pd.DataFrame([{"powod": k, "wiersze": v} for k, v in liczniki.items()])
    raport.to_csv(katalog / "raport_czyszczenia.csv", index=False)

    wiersze = []
    for (wojewodztwo, uzytek, gotowy), liczba in sorted(rozklad.items()):
        wiersze.append(
            {
                "wojewodztwo": wojewodztwo,
                "sposob_uzytkowania": uzytek,
                "do_modelu": gotowy,
                "liczba": liczba,
            }
        )

    kolumny = ["wojewodztwo", "sposob_uzytkowania", "do_modelu", "liczba"]
    grupy = pd.DataFrame(wiersze, columns=kolumny)
    grupy.to_csv(katalog / "rozklad_gruntow.csv", index=False)

    wojewodztwa = Counter()
    for (woj, _, _), ile in rozklad.items():
        wojewodztwa[woj] += ile

    opis["wiersze_wg_wojewodztwa"] = dict(sorted(wojewodztwa.items()))
    (katalog / "podsumowanie.json").write_text(
        json.dumps(opis, ensure_ascii=False, indent=2) + "\n"
    )
    print(raport.to_string(index=False))
