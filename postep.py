"""Podglad pobierania ULDK. Ctrl+C zamyka tylko licznik, nie pobieranie."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import config

if __name__ == "__main__":
    plik = Path(config.SCIEZKA_POSREDNIE) / "uldk_postep.json"
    poczatek = None
    pierwsza_liczba = None

    print("Postep ULDK — odswiezanie co 10 sekund. Ctrl+C zamyka podglad.\n")

    try:
        while True:
            try:
                stan = json.loads(plik.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                print("Czekam na zapis postepu...", flush=True)
                time.sleep(10)
                continue

            wykonane = stan["sprawdzone"]
            wszystkie = stan["dzialki_do_sprawdzenia"]
            zostalo = max(0, wszystkie - wykonane)
            procent = 100 * wykonane / wszystkie if wszystkie else 100

            aktualizacja = datetime.fromisoformat(stan["aktualizacja_utc"])

            if pierwsza_liczba is None or wykonane < pierwsza_liczba:
                pierwsza_liczba = wykonane
                poczatek = aktualizacja

            czas = (aktualizacja - poczatek).total_seconds()
            przyrost = wykonane - pierwsza_liczba
            eta = "zbieram pomiar tempa..."

            if przyrost > 0 and czas >= 10:
                sekundy = zostalo * czas / przyrost
                godziny = int(sekundy // 3600)
                minuty = int(sekundy % 3600 // 60)
                eta = f"ok. {godziny} godz. {minuty} min (samo pobieranie)"

            opoznienie = (datetime.now(timezone.utc) - aktualizacja).total_seconds()

            if opoznienie > 120:
                eta = "brak nowego postepu od ponad 2 min — sprawdz log"

            print(
                f"{datetime.now():%H:%M:%S} | {wykonane:,}/{wszystkie:,} ({procent:.2f}%)"
                f" | zostalo: {zostalo:,} | granice: {stan['granice_dostepne']:,}"
                f" | do konca: {eta} | {stan['status']}",
                flush=True,
            )

            if stan["status"] in {"zakonczone", "przerwane"}:
                if stan.get("blad"):
                    print(stan["blad"])
                break

            if stan["status"] == "przeliczanie":
                print(
                    "Pobieranie skonczone. Przeliczanie calego RCN zwykle trwa ok. 6 minut.",
                    flush=True,
                )

            time.sleep(10)

    except KeyboardInterrupt:
        print("\nPodglad zamkniety. Pobieranie dziala niezaleznie.")
