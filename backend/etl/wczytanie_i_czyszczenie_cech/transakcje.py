import hashlib
import json
import sqlite3


# Ten indeks ma widziec caly plik, nawet gdy dzialki transakcji sa w innych partiach.
def zbuduj_indeks(parquet, sciezka, wielkosc_partii, sprawdz_miejsce):
    baza = sqlite3.connect(sciezka)
    baza.execute("PRAGMA cache_size = -32768")
    baza.execute("PRAGMA temp_store = FILE")
    baza.execute("""CREATE TABLE transakcje (
        klucz TEXT PRIMARY KEY, pierwszy INTEGER, ile INTEGER,
        dzialka TEXT, wersja TEXT, podpis BLOB,
        brak_dzialki INTEGER, wiele_dzialek INTEGER,
        wiele_wersji INTEGER, sprzeczne INTEGER
    ) WITHOUT ROWID""")

    sql = """INSERT INTO transakcje VALUES (?, ?, 1, ?, ?, ?, ?, 0, 0, 0)
        ON CONFLICT(klucz) DO UPDATE SET
            ile = ile + 1,
            brak_dzialki = brak_dzialki OR excluded.brak_dzialki,
            wiele_dzialek = wiele_dzialek OR dzialka != excluded.dzialka,
            wiele_wersji = wiele_wersji OR wersja != excluded.wersja,
            sprzeczne = sprzeczne OR podpis != excluded.podpis"""

    kolumny = [
        k
        for k in parquet.schema_arrow.names
        if k not in {"gid", "geometry_bbox", "serwis_rcn"}
    ]
    pozycja = 0
    brak_klucza = 0

    try:
        for partia in parquet.iter_batches(batch_size=wielkosc_partii, columns=kolumny):
            sprawdz_miejsce()
            df = partia.to_pandas()
            for k in [
                "tran_przestrzen_nazw",
                "tran_lokalny_id_iip",
                "dzi_id_dzialki",
                "tran_wersja_id",
            ]:
                df[k] = df[k].fillna("").astype(str).str.strip()

            numery = {k: i for i, k in enumerate(df.columns)}
            wpisy = []

            for offset, wiersz in enumerate(df.itertuples(index=False, name=None)):
                przestrzen = wiersz[numery["tran_przestrzen_nazw"]]
                lokalny = wiersz[numery["tran_lokalny_id_iip"]]

                if not przestrzen or not lokalny:
                    brak_klucza += 1
                    continue

                klucz = json.dumps(
                    [przestrzen, lokalny], ensure_ascii=False, separators=(",", ":")
                )
                dzialka = wiersz[numery["dzi_id_dzialki"]]
                wersja = wiersz[numery["tran_wersja_id"]]
                tresc = json.dumps(
                    wiersz, default=str, ensure_ascii=False, separators=(",", ":")
                )
                podpis = hashlib.sha256(tresc.encode()).digest()
                wpisy.append(
                    (klucz, pozycja + offset, dzialka, wersja, podpis, int(not dzialka))
                )

            with baza:
                baza.executemany(sql, wpisy)

            pozycja += len(df)
            if pozycja % (wielkosc_partii * 20) == 0:
                print(
                    f"  indeks: {pozycja:,} / {parquet.metadata.num_rows:,}", flush=True
                )

        sprawdz_miejsce()
        baza.execute("CREATE INDEX pozycje ON transakcje(pierwszy)")
        baza.commit()
        return baza, brak_klucza

    except BaseException:
        baza.close()
        raise


def podsumuj_indeks(baza, brak_klucza):
    wynik = {"brak_klucza_transakcji": brak_klucza}
    # Rozne wersje bez historii skladowej nie daja pewnego obrazu transakcji.
    powody = [
        ("rozne_wersje_transakcji", "wiele_wersji = 1"),
        ("niepelny_sklad_transakcji", "brak_dzialki = 1"),
        ("transakcja_wielodzialkowa", "wiele_dzialek = 1"),
        ("sprzeczne_wpisy_transakcji", "sprzeczne = 1"),
    ]

    warunek = "1=1"
    for powod, odrzucone in powody:
        ile = baza.execute(
            f"SELECT coalesce(sum(ile), 0) FROM transakcje WHERE {warunek} AND {odrzucone}"
        ).fetchone()[0]
        wynik[powod] = ile
        warunek += f" AND NOT ({odrzucone})"

    wynik["powtorzone_wiersze"] = baza.execute(
        f"SELECT coalesce(sum(ile - 1), 0) FROM transakcje WHERE {warunek}"
    ).fetchone()[0]
    return wynik
