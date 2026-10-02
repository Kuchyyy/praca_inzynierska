import json
from collections import Counter

import pandas as pd


def zapisz_raport(katalog, liczniki, rozklad, opis):
    raport = pd.DataFrame([{'powod': k, 'wiersze': v} for k, v in liczniki.items()])
    raport.to_csv(katalog / 'raport_czyszczenia.csv', index=False)
    grupy = pd.DataFrame([
        {'wojewodztwo': woj, 'sposob_uzytkowania': uzytek, 'liczba': ile}
        for (woj, uzytek), ile in sorted(rozklad.items())
    ], columns=['wojewodztwo', 'sposob_uzytkowania', 'liczba'])
    grupy.to_csv(katalog / 'rozklad_gruntow.csv', index=False)
    wojewodztwa = Counter()
    for (woj, _), ile in rozklad.items():
        wojewodztwa[woj] += ile
    opis['wiersze_wg_wojewodztwa'] = dict(sorted(wojewodztwa.items()))
    (katalog / 'podsumowanie.json').write_text(json.dumps(opis, ensure_ascii=False, indent=2) + '\n')
    print(raport.to_string(index=False))
