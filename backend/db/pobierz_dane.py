import shutil
from pathlib import Path
from urllib.request import urlopen

import config

PLIKI = [
    (
        "https://opendata.geoportal.gov.pl/InneDane/latest_exports/rcn_transakcje_ceny/PARQUET/0_transakcje_ceny_dzialki.parquet",
        config.SCIEZKA_SUROWE,
    ),
    (
        "https://download.geofabrik.de/europe/poland-260930.osm.pbf",
        config.SCIEZKA_OSM,
    ),
]


def pobierz_dane():
    for adres, sciezka in PLIKI:
        cel = Path(sciezka)
        if cel.exists():
            print(f"Już pobrany: {cel}")
            continue

        cel.parent.mkdir(parents=True, exist_ok=True)
        roboczy = cel.with_suffix(".czesc")
        print(f"Pobieram {adres}", flush=True)
        with urlopen(adres, timeout=120) as odpowiedz, roboczy.open("wb") as zapis:
            shutil.copyfileobj(odpowiedz, zapis)
        roboczy.rename(cel)
        print(f"Zapisano: {cel}")


if __name__ == "__main__":
    pobierz_dane()
