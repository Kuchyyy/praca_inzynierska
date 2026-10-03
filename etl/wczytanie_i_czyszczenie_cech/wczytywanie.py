import json
import shutil
import time
from collections import Counter
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import CRS

import config
from etl.uldk.granice import otworz_cache
from etl.uldk.srodki import wczytaj_zapis
from etl.wczytanie_i_czyszczenie_cech.czyszczenie import wyczysc_partie
from etl.wczytanie_i_czyszczenie_cech.raport import zapisz_raport
from etl.wczytanie_i_czyszczenie_cech.transakcje import podsumuj_indeks, zbuduj_indeks


def oczysc_plik(
    wejscie, wyjscie, data_do, wielkosc_partii=25000, wojewodztwo=None, limit_uldk=0
):
    wejscie, wyjscie = Path(wejscie), Path(wyjscie)
    if wyjscie.exists():
        raise FileExistsError(
            f"Wynik juz istnieje: {wyjscie}. Ustaw inny katalog wyniku w config.py."
        )
    if limit_uldk < 0:
        raise ValueError("Limit ULDK nie moze byc ujemny")
    if wielkosc_partii < 1:
        raise ValueError("Wielkosc partii musi byc dodatnia")
    if data_do > date.today() or data_do.year < config.ROK_OD:
        raise ValueError("Data odciecia musi byc miedzy poczatkiem badania a dzisiaj")

    parquet = pq.ParquetFile(wejscie)
    wymagane = set(config.KOLUMNY_POTRZEBNE)
    brak = wymagane - set(parquet.schema_arrow.names)
    if brak:
        raise ValueError(f"Brak kolumn: {sorted(brak)}")

    geo = json.loads((parquet.schema_arrow.metadata or {}).get(b"geo", b"{}"))
    kolumna_geo = geo.get("columns", {}).get("geometry", {})
    if (
        kolumna_geo.get("encoding") != "WKB"
        or kolumna_geo.get("crs") is None
        or CRS.from_user_input(kolumna_geo["crs"]).to_epsg() != 2180
    ):
        raise ValueError("Oczekiwany GeoParquet z geometria WKB w EPSG:2180")

    stan_zrodla = (wejscie.stat().st_size, wejscie.stat().st_mtime_ns)
    wyjscie.parent.mkdir(parents=True, exist_ok=True)

    def sprawdz_miejsce():
        if (
            shutil.disk_usage(wyjscie.parent).free
            < config.ZAPAS_DYSKU_GIB * 1024**3 + 256 * 1024**2
        ):
            raise RuntimeError(
                f"Przerwano: potrzeba {config.ZAPAS_DYSKU_GIB} GiB wolnego miejsca"
            )

    sprawdz_miejsce()
    start = time.monotonic()
    print(f"Wejscie: {wejscie}, {parquet.metadata.num_rows:,} wierszy", flush=True)
    print("Przebieg 1/2: sklad transakcji i duplikaty", flush=True)

    with TemporaryDirectory(prefix=".czyszczenie-", dir=wyjscie.parent) as tymczasowy:
        roboczy = Path(tymczasowy)
        baza, brak_klucza = zbuduj_indeks(
            parquet, roboczy / "indeks.sqlite", wielkosc_partii, sprawdz_miejsce
        )

        writer = None
        baza_uldk = None

        try:
            srodki = wczytaj_zapis()
            baza_uldk = otworz_cache(config.SCIEZKA_ULDK_GRANICE)
            pobieranie = {"pozostalo": limit_uldk, "zapytania": 0, "pobrane": 0}

            liczniki = Counter(podsumuj_indeks(baza, brak_klucza))
            rozklad = Counter()
            zrodla_powierzchni = Counter()
            lata = Counter()
            udzialy = Counter()
            srodki_zrodla = Counter()
            statusy_jakosci = Counter()

            kolumny = config.KOLUMNY_POTRZEBNE
            tekstowe = [
                "teryt_woj",
                "teryt_powiat",
                "teryt_gmina",
                "teryt_obreb",
                "status_udzialu",
                "status_geometrii",
                "zrodlo_powierzchni",
                "klucz_transakcji",
                "zrodlo_geometrii",
                "zrodlo_srodka",
                "uldk_pobrano_utc",
                "status_jakosci",
                "powody_wstrzymania",
            ]
            liczbowe = [
                "pole_geom_m2",
                "obwod_m",
                "x_2180",
                "y_2180",
                "powierzchnia_m2",
                "cena_m2",
                "udzial_sprzedany",
            ]
            logiczne = ["ma_srodek", "cena_przeliczona_z_udzialu", "do_modelu"]

            pola = []
            for nazwa in kolumny:
                pola.append(parquet.schema_arrow.field(nazwa))

            for nazwa in tekstowe:
                pola.append(pa.field(nazwa, pa.string()))

            for nazwa in liczbowe:
                pola.append(pa.field(nazwa, pa.float64()))

            pola.append(pa.field("rok", pa.int32()))
            for nazwa in logiczne:
                pola.append(pa.field(nazwa, pa.bool_()))

            schemat = pa.schema(pola)

            # Stary bbox opisuje surowy plik, a nie wynik filtrowania.
            opis_geometrii = kolumna_geo.copy()
            for nazwa in ["bbox", "covering", "orientation", "geometry_types"]:
                opis_geometrii.pop(nazwa, None)

            opis_geometrii["geometry_types"] = ["Polygon", "MultiPolygon"]
            geo_wyniku = {
                "version": geo["version"],
                "primary_column": "geometry",
                "columns": {"geometry": opis_geometrii},
            }

            schemat = schemat.with_metadata({b"geo": json.dumps(geo_wyniku).encode()})

            wynik = roboczy / "wynik"
            wynik.mkdir()
            writer = pq.ParquetWriter(
                wynik / "transakcje.parquet", schemat, compression="zstd"
            )

            print("Przebieg 2/2: filtry, geometria i zapis partiami", flush=True)
            pozycja = 0
            zapisano = 0

            for partia in parquet.iter_batches(
                batch_size=wielkosc_partii, columns=kolumny
            ):
                sprawdz_miejsce()
                zapytanie = """
                    SELECT pierwszy FROM transakcje
                    WHERE pierwszy >= ? AND pierwszy < ?
                      AND brak_dzialki = 0 AND wiele_dzialek = 0
                      AND wiele_wersji = 0 AND sprzeczne = 0
                    ORDER BY pierwszy
                """
                zakres = (pozycja, pozycja + len(partia))
                indeksy = []

                for wiersz in baza.execute(zapytanie, zakres):
                    indeksy.append(wiersz[0] - pozycja)

                pozycja += len(partia)
                if not indeksy:
                    continue

                df = partia.take(pa.array(indeksy, type=pa.int64())).to_pandas()
                df = wyczysc_partie(
                    df, data_do, liczniki, wojewodztwo, srodki, baza_uldk, pobieranie
                )

                if not df.empty:
                    tabela = pa.Table.from_pandas(
                        df, schema=schemat, preserve_index=False
                    )
                    writer.write_table(tabela)
                    zapisano += len(df)

                    rozklad.update(
                        df.groupby(
                            [
                                "teryt_woj",
                                df["dzi_sposob_uzyt"].fillna("brak_danych"),
                                "do_modelu",
                            ]
                        )
                        .size()
                        .to_dict()
                    )
                    zrodla_powierzchni.update(
                        df["zrodlo_powierzchni"].value_counts().to_dict()
                    )
                    udzialy.update(df["status_udzialu"].value_counts().to_dict())
                    srodki_zrodla.update(df["zrodlo_srodka"].value_counts().to_dict())
                    statusy_jakosci.update(
                        df["status_jakosci"].value_counts().to_dict()
                    )
                    lata.update(
                        {str(k): v for k, v in df["rok"].value_counts().items()}
                    )

                if pozycja % (wielkosc_partii * 20) == 0:
                    print(
                        f"  odczytano: {pozycja:,}, zapisano: {zapisano:,}", flush=True
                    )

            writer.close()
            writer = None
            liczniki["zachowane"] = zapisano
            if sum(liczniki.values()) != parquet.metadata.num_rows:
                raise RuntimeError("Raport nie bilansuje liczby wierszy")
            if stan_zrodla != (wejscie.stat().st_size, wejscie.stat().st_mtime_ns):
                raise RuntimeError("Plik zrodlowy zmienil sie podczas obliczen")

            zapisz_raport(
                wynik,
                liczniki,
                rozklad,
                {
                    "plik_zrodlowy": str(wejscie.resolve()),
                    "bajty_zrodla": stan_zrodla[0],
                    "data_do": data_do.isoformat(),
                    "rok_od": config.ROK_OD,
                    "wojewodztwo": wojewodztwo,
                    "wielkosc_partii": wielkosc_partii,
                    "wiersze_surowe": parquet.metadata.num_rows,
                    "wiersze_wynikowe": zapisano,
                    "zrodla_powierzchni": dict(zrodla_powierzchni),
                    "lata": dict(sorted(lata.items())),
                    "status_udzialu": dict(udzialy),
                    "zrodla_srodkow": dict(srodki_zrodla),
                    "status_jakosci": dict(statusy_jakosci),
                    "uldk_zapytania": pobieranie["zapytania"],
                    "uldk_pobrane_granice": pobieranie["pobrane"],
                    "czas_sekundy": round(time.monotonic() - start, 2),
                    "rozmiar_parquet_bajty": (wynik / "transakcje.parquet")
                    .stat()
                    .st_size,
                    "zasady": "Jedna dzialka i spojna wersja; nieznane udzialy odrzucone; cena_m2 = cena / (powierzchnia * udzial); do_modelu wymaga zweryfikowanej powierzchni. Srodki z cache nie potwierdzaja powierzchni.",
                },
            )

            sprawdz_miejsce()
            wynik.rename(wyjscie)

        finally:
            if writer is not None:
                writer.close()
            baza.close()
            if baza_uldk is not None:
                baza_uldk.close()

    print(f"Zapisano: {wyjscie}. Indeks tymczasowy usuniety.", flush=True)
    return wyjscie
