"""Uzupelnianie brakujacych granic z gotowego zbioru, ze wznowieniem z cache."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

import config
from etl.uldk.granice import otworz_cache, znajdz_granice
from etl.wczytanie_i_czyszczenie_cech.wczytywanie import oczysc_plik


def pobierz_brakujace_granice():
    wejscie = Path(config.SCIEZKA_OCZYSZCZONE)
    wyjscie = Path(config.SCIEZKA_PO_ULDK)

    if wyjscie.exists():
        raise FileExistsError(f"Wynik juz istnieje: {wyjscie}")

    opis = json.loads((wejscie / "podsumowanie.json").read_text())

    identyfikatory = set()

    for partia in pq.ParquetFile(wejscie / "transakcje.parquet").iter_batches(
        columns=["dzi_id_dzialki", "zrodlo_powierzchni"]
    ):
        for r in partia.to_pylist():
            if r["zrodlo_powierzchni"] == "brak_geometrii_do_weryfikacji":
                identyfikatory.add(r["dzi_id_dzialki"])

    identyfikatory = sorted(identyfikatory)

    baza = otworz_cache(config.SCIEZKA_ULDK_GRANICE)
    pobieranie = {"pozostalo": len(identyfikatory), "zapytania": 0, "pobrane": 0}

    postep = Path(config.SCIEZKA_POSREDNIE) / "uldk_postep.json"
    stan = {
        "dzialki_do_sprawdzenia": len(identyfikatory),
        "sprawdzone": 0,
        "granice_dostepne": 0,
        "status": "pobieranie",
        "wyjscie": str(wyjscie),
    }
    print(f"Dzialki do sprawdzenia: {len(identyfikatory):,}", flush=True)

    try:
        for start in range(0, len(identyfikatory), 20):
            czesc = identyfikatory[start : start + 20]
            granice = znajdz_granice(czesc, baza, pobieranie)

            stan["sprawdzone"] += len(czesc)
            stan["granice_dostepne"] += len(granice)
            stan.update(pobieranie)
            stan["aktualizacja_utc"] = datetime.now(timezone.utc).isoformat()
            postep.with_suffix(".part").write_text(json.dumps(stan, indent=2))
            postep.with_suffix(".part").replace(postep)

            # Przy awarii sieci nie przemielamy calej Polski bez wynikow.
            statusy = [
                baza.execute("SELECT status FROM granice WHERE id=?", (i,)).fetchone()
                for i in czesc
            ]
            if len(czesc) == 20 and all(s and s[0] == "blad_sieci" for s in statusy):
                raise RuntimeError(
                    "20 kolejnych bledow sieci. Cache zachowany; wznow po przywroceniu polaczenia."
                )

        stan["status"] = "granice_pobrane"
        return opis

    except BaseException as blad:
        stan["status"] = "przerwane"
        stan["blad"] = str(blad)
        raise

    finally:
        baza.close()
        stan["aktualizacja_utc"] = datetime.now(timezone.utc).isoformat()
        postep.write_text(json.dumps(stan, indent=2))


def przelicz_po_uldk(opis):
    postep = Path(config.SCIEZKA_POSREDNIE) / "uldk_postep.json"
    stan = json.loads(postep.read_text())

    try:
        stan["status"] = "przeliczanie"
        postep.write_text(json.dumps(stan, indent=2))

        oczysc_plik(
            wejscie=opis["plik_zrodlowy"],
            wyjscie=config.SCIEZKA_PO_ULDK,
            data_do=date.fromisoformat(opis["data_do"]),
            wielkosc_partii=opis["wielkosc_partii"],
            wojewodztwo=opis["wojewodztwo"],
            limit_uldk=0,
        )

        stan["status"] = "zakonczone"

    except BaseException as blad:
        stan["status"] = "przerwane"
        stan["blad"] = str(blad)
        raise

    finally:
        stan["aktualizacja_utc"] = datetime.now(timezone.utc).isoformat()
        postep.write_text(json.dumps(stan, indent=2))


if __name__ == "__main__":
    opis = pobierz_brakujace_granice()
    przelicz_po_uldk(opis)
