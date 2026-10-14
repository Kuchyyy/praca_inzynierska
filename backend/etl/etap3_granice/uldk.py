import time
from datetime import datetime, timezone

import config
from etl.etap3_granice.granice import brakujace_dzialki, otworz_cache, pobierz_granice


def uzupelnij_uldk():
    baza = otworz_cache(config.SCIEZKA_ULDK_GRANICE)

    sprawdzone = set()
    for identyfikator, status in baza.execute("SELECT id, status FROM granice"):
        if status != "blad_sieci":
            sprawdzone.add(identyfikator)
    for (identyfikator,) in baza.execute("SELECT id FROM granice_egib"):
        sprawdzone.add(identyfikator)

    do_pobrania = [i for i in brakujace_dzialki(config.SCIEZKA_OCZYSZCZONE) if i not in sprawdzone]
    print(f"Działki do sprawdzenia w ULDK: {len(do_pobrania):,}")

    bledy_z_rzedu = 0
    for numer, identyfikator in enumerate(do_pobrania, 1):
        geometria, status = pobierz_granice(identyfikator)
        kiedy = datetime.now(timezone.utc).isoformat()
        with baza:
            baza.execute("INSERT OR REPLACE INTO granice VALUES (?, ?, ?, ?)", (identyfikator, geometria, kiedy, status))

        if numer % 100 == 0:
            print(f"  ULDK: {numer:,}/{len(do_pobrania):,}", flush=True)

        if status == "blad_sieci":
            bledy_z_rzedu += 1
            time.sleep(2)
        else:
            bledy_z_rzedu = 0
            time.sleep(config.PRZERWA_ULDK)

        if bledy_z_rzedu == 20:
            baza.close()
            raise RuntimeError("20 błędów sieci z rzędu. Pobrane granice są w cache, uruchom ponownie później.")

    baza.close()
