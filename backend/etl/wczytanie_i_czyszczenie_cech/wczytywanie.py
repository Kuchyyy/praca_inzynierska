from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow as pa
import pyarrow.parquet as pq

import config
from etl.uldk.granice import otworz_cache
from etl.wczytanie_i_czyszczenie_cech.czyszczenie import wyczysc_partie
from etl.wczytanie_i_czyszczenie_cech.transakcje import podsumuj_indeks, zbuduj_indeks

TEKSTOWE = ["teryt_woj", "teryt_powiat", "teryt_gmina", "teryt_obreb", "status_udzialu", "zrodlo_geometrii", "zrodlo_powierzchni", "klucz_transakcji"]
LICZBOWE = ["udzial_sprzedany", "pole_geom_m2", "obwod_m", "x_2180", "y_2180", "powierzchnia_m2", "cena_m2"]

ZAPYTANIE = """
    SELECT pierwszy FROM transakcje
    WHERE pierwszy >= ? AND pierwszy < ?
      AND brak_dzialki = 0 AND wiele_dzialek = 0 AND wiele_wersji = 0 AND sprzeczne = 0
    ORDER BY pierwszy
"""


def oczysc_plik(wejscie, wyjscie):
    parquet = pq.ParquetFile(wejscie)
    print(f"Wejście: {wejscie}, {parquet.metadata.num_rows:,} wierszy")

    pola = [parquet.schema_arrow.field(nazwa) for nazwa in config.KOLUMNY_POTRZEBNE]
    pola += [pa.field(nazwa, pa.string()) for nazwa in TEKSTOWE]
    pola += [pa.field(nazwa, pa.float64()) for nazwa in LICZBOWE]
    pola += [pa.field("do_modelu", pa.bool_()), pa.field("rok", pa.int32())]
    schemat = pa.schema(pola)

    wyjscie = Path(wyjscie)
    wyjscie.parent.mkdir(parents=True, exist_ok=True)
    roboczy = wyjscie.with_suffix(".czesc")

    with TemporaryDirectory() as katalog:
        print("Przebieg 1/2: skład transakcji i duplikaty")
        indeks, brak_klucza = zbuduj_indeks(parquet, Path(katalog) / "indeks.sqlite", config.WIELKOSC_PARTII)
        liczniki = Counter(podsumuj_indeks(indeks, brak_klucza))
        baza_uldk = otworz_cache(config.SCIEZKA_ULDK_GRANICE)

        print("Przebieg 2/2: filtry, geometria i zapis partiami")
        pozycja = 0
        zapisano = 0
        with pq.ParquetWriter(roboczy, schemat, compression="zstd") as zapis:
            for partia in parquet.iter_batches(batch_size=config.WIELKOSC_PARTII, columns=config.KOLUMNY_POTRZEBNE):
                zakres = (pozycja, pozycja + len(partia))
                indeksy = [wiersz[0] - pozycja for wiersz in indeks.execute(ZAPYTANIE, zakres)]
                pozycja += len(partia)
                if not indeksy:
                    continue

                df = partia.take(pa.array(indeksy, type=pa.int64())).to_pandas()
                df = wyczysc_partie(df, liczniki, baza_uldk)
                if not df.empty:
                    zapis.write_table(pa.Table.from_pandas(df, schema=schemat, preserve_index=False))
                    zapisano += len(df)

                if pozycja % (config.WIELKOSC_PARTII * 20) == 0:
                    print(f"  odczytano: {pozycja:,}, zapisano: {zapisano:,}", flush=True)

        indeks.close()
        baza_uldk.close()

    roboczy.rename(wyjscie)
    liczniki["zachowane"] = zapisano
    print("Ile wierszy odpadło i dlaczego:")
    for powod, ile in liczniki.items():
        print(f"  {powod:<30} {ile:>10,}")
    print(f"Zapisano: {wyjscie}")
