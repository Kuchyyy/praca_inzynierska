"""Pobranie zrodel Polski: python db/pobierz_dane.py (z katalogu projektu)."""

import hashlib
import json
import shutil
import struct
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pyarrow.parquet as pq


KATALOG = Path(__file__).resolve().parent / "dane"
ZAPAS = 10 * 1024**3
PLIKI = [
    (
        "https://opendata.geoportal.gov.pl/InneDane/latest_exports/"
        "rcn_transakcje_ceny/PARQUET/0_transakcje_ceny_dzialki.parquet",
        "surowe/rcn/0_transakcje_ceny_dzialki.parquet",
    ),
    (
        "https://download.geofabrik.de/europe/poland-260930.osm.pbf",
        "surowe/osm/poland-260930.osm.pbf",
    ),
]


def sprawdz(plik, oczekiwany_md5):
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    with plik.open("rb") as dane:
        while kawalek := dane.read(8 * 1024**2):
            sha256.update(kawalek)
            md5.update(kawalek)
    if oczekiwany_md5 and md5.hexdigest() != oczekiwany_md5:
        raise ValueError(f"Nie zgadza sie suma MD5: {plik}")

    if ".parquet" in plik.name:
        parquet = pq.ParquetFile(plik)
        wymagane = {"tran_lokalny_id_iip", "tran_przestrzen_nazw", "dzi_id_dzialki", "geometry"}
        if not wymagane.issubset(parquet.schema_arrow.names):
            raise ValueError("Nieoczekiwany schemat RCN")
        geo = json.loads(parquet.schema_arrow.metadata[b"geo"])
        proba = next(parquet.iter_batches(batch_size=5))
        print(f"  RCN: {parquet.metadata.num_rows:,} wierszy, {len(parquet.schema_arrow)} kolumn", flush=True)
        print(f"  GeoParquet {geo['version']}, proba: {proba.num_rows} wierszy", flush=True)
    else:
        with plik.open("rb") as dane:
            rozmiar = struct.unpack(">I", dane.read(4))[0]
            if not 0 < rozmiar <= 65536:
                raise ValueError("Nieprawidlowy rozmiar naglowka PBF")
            naglowek = dane.read(rozmiar)
            if not naglowek.startswith(b"\x0a\x09OSMHeader"):
                raise ValueError("Brak OSMHeader w PBF")
        print(f"  PBF: OSMHeader ({rozmiar} bajtow), MD5 zgodne z Geofabrik", flush=True)
    return sha256.hexdigest()


def pobierz():
    KATALOG.mkdir(parents=True, exist_ok=True)
    wykaz = KATALOG / "zrodla.json"
    zrodla = json.loads(wykaz.read_text()) if wykaz.exists() else {}

    for url, nazwa in PLIKI:
        cel = KATALOG / nazwa
        cel.parent.mkdir(parents=True, exist_ok=True)
        czesc = cel.with_suffix(cel.suffix + ".part")
        opis = czesc.with_suffix(czesc.suffix + ".json")
        with urlopen(Request(url, method="HEAD"), timeout=60) as odpowiedz:
            rozmiar = int(odpowiedz.headers["Content-Length"])
            etag = odpowiedz.headers.get("ETag")
            zmieniony = odpowiedz.headers.get("Last-Modified")
            wersja = {"url": odpowiedz.url, "rozmiar": rozmiar, "etag": etag, "last_modified": zmieniony}

        md5 = None
        if nazwa.endswith(".pbf"):
            with urlopen(url + ".md5", timeout=60) as odpowiedz:
                md5 = odpowiedz.read(4096).decode().split()[0]

        if cel.exists():
            # Gotowych danych nie nadpisujemy nowym eksportem z serwera.
            zapis = zrodla.get(nazwa)
            if not zapis:
                raise RuntimeError(f"Plik juz istnieje bez wpisu w wykazie: {cel}")
            if cel.stat().st_size != zapis["rozmiar"]:
                raise ValueError(f"Zmieniony rozmiar lokalnego pliku: {cel}")
            suma = sprawdz(cel, zapis.get("md5"))
            if suma != zapis["sha256"]:
                raise ValueError(f"Zmieniona zawartosc lokalnego pliku: {cel}")
            print(f"Juz pobrany i sprawdzony: {cel.name}", flush=True)
            continue

        walidator = etag if etag and not etag.startswith("W/") else zmieniony
        zgodna = opis.exists() and json.loads(opis.read_text()) == wersja
        start = czesc.stat().st_size if czesc.exists() and zgodna and walidator else 0
        if start > rozmiar:
            raise ValueError("Plik czesciowy jest wiekszy od zrodla")
        if shutil.disk_usage(KATALOG).free - (rozmiar - start) < ZAPAS:
            raise RuntimeError("Za malo miejsca: po pobraniu musi zostac 10 GiB")
        print(f"Pobieram {cel.name}: {rozmiar:,} bajtow, wznowienie od {start:,}", flush=True)

        if start != rozmiar:
            naglowki = {"Range": f"bytes={start}-", "If-Range": walidator} if start else {}
            with urlopen(Request(url, headers=naglowki), timeout=120) as odpowiedz:
                if start and (odpowiedz.status != 206 or not odpowiedz.headers.get("Content-Range", "").startswith(f"bytes {start}-")):
                    raise RuntimeError("Serwer nie potwierdzil wznowienia tej samej wersji")
                if int(odpowiedz.headers.get("Content-Length", rozmiar - start)) != rozmiar - start:
                    raise RuntimeError("Rozmiar zrodla zmienil sie przed pobraniem")
                if walidator and odpowiedz.headers.get("ETag" if walidator == etag else "Last-Modified") != walidator:
                    raise RuntimeError("Wersja zrodla zmienila sie przed pobraniem")
                opis.write_text(json.dumps(wersja, indent=2) + "\n")
                with czesc.open("ab" if start else "wb") as dane:
                    zapisano = start
                    ostatni_raport = start
                    while kawalek := odpowiedz.read(4 * 1024**2):
                        if shutil.disk_usage(KATALOG).free - len(kawalek) < ZAPAS:
                            raise RuntimeError("Przerwano pobieranie, zostawiam 10 GiB zapasu")
                        dane.write(kawalek)
                        zapisano += len(kawalek)
                        if zapisano - ostatni_raport >= 256 * 1024**2:
                            print(f"  {100 * zapisano / rozmiar:.0f}%", flush=True)
                            ostatni_raport = zapisano

        if czesc.stat().st_size != rozmiar:
            raise ValueError("Niepelny plik, pozostawiam .part")
        suma = sprawdz(czesc, md5)
        zrodla[nazwa] = {**wersja, "pobrano_utc": datetime.now(timezone.utc).isoformat(), "sha256": suma, "md5": md5}
        # Wpis przed zmiana nazwy pozwala dokonczyc zapis po przerwaniu.
        tymczasowy = wykaz.with_suffix(".json.part")
        tymczasowy.write_text(json.dumps(zrodla, indent=2, ensure_ascii=False) + "\n")
        tymczasowy.replace(wykaz)
        czesc.rename(cel)
        opis.unlink()
        print(f"Zapisano {cel.name}. Wolne: {shutil.disk_usage(KATALOG).free / 1024**3:.2f} GiB", flush=True)


if __name__ == "__main__":
    pobierz()
