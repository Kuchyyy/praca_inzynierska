"""Podglad pobierania ULDK. Ctrl+C zamyka tylko licznik, nie pobieranie."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import config

if __name__ == "__main__":
    plik = Path(config.SCIEZKA_POSREDNIE) / "uldk_postep.json"
    egib = Path(config.SCIEZKA_POSREDNIE) / "egib_postep.json"
    if egib.exists():
        plik = egib

    osm = Path(config.SCIEZKA_POSREDNIE) / "osm_postep.json"
    if osm.exists():
        plik = osm

    poczatek = None
    pierwsza_liczba = None

    print("Postep danych — odswiezanie co 10 sekund. Ctrl+C zamyka podglad.\n")

    try:
        while True:
            try:
                stan = json.loads(plik.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                print("Czekam na zapis postepu...", flush=True)
                time.sleep(10)
                continue

            if plik == osm:
                if stan["status"] == "odczyt_osm":
                    print(f"OSM: {stan['obiekty']:,} obiektow odczytanych | czas: {stan['czas_sekundy']} s | trwa budowanie warstw, ETA jeszcze nieznane", flush=True)
                elif stan["status"] == "cechy_osm":
                    print(f"OSM: {stan['wykonane']}/{stan['wszystkie']} warstw | licze: {stan['warstwa']} | czas: {stan['czas_sekundy']} s", flush=True)
                else:
                    print(stan, flush=True)
                    if stan["status"] in {"zakonczone", "przerwane"}:
                        break
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

            if "eta_sekundy" in stan:
                sekundy = stan["eta_sekundy"]
                eta = f"ok. {int(sekundy // 3600)} godz. {int(sekundy % 3600 // 60)} min (paczki)"

            if "powiaty" in stan:
                print(f"Powiaty: {stan['powiaty_gotowe']}/{stan['powiaty']} | obecny: {stan.get('powiat', '-')} | bledy: {len(stan.get('bledy', {}))}")

            opoznienie = (datetime.now(timezone.utc) - aktualizacja).total_seconds()

            if opoznienie > (600 if "powiaty" in stan else 120):
                eta = "dlugo bez aktualizacji — sprawdz log"

            print(
                f"{datetime.now():%H:%M:%S} | {wykonane:,}/{wszystkie:,} ({procent:.2f}%)"
                f" | zostalo: {zostalo:,} | granice: {stan['granice_dostepne']:,}"
                f" | do konca: {eta} | {stan['status']}",
                flush=True,
            )

            if stan["status"] in {"zakonczone", "zakonczone_z_bledami", "przerwane"}:
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
