import re
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

import osmium
import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import Transformer
from shapely import wkb
from shapely.ops import transform

import config


WARSTWY = ["budynki", "drogi", "utwardzone", "las", "miasta_50k", "poi"]


def wybierz_warstwy(tagi, typ):
    warstwy = []
    droga = tagi.get("highway", "")
    budynek = tagi.get("building", "")
    ludnosc = re.sub(r"[\s,]", "", tagi.get("population", ""))
    ludnosc = int(ludnosc) if ludnosc.isdigit() else None

    if typ == "linia":
        wykluczone = {"footway", "path", "steps", "track", "cycleway", "bridleway", "proposed", "construction", "platform"}
        if droga and droga not in wykluczone:
            warstwy.append("drogi")
            if tagi.get("surface") in {"asphalt", "concrete", "paving_stones", "sett", "paved", "concrete:plates", "concrete:lanes"}:
                warstwy.append("utwardzone")

    if typ == "obszar":
        if budynek and budynek != "no":
            warstwy.append("budynki")
        if tagi.get("landuse") == "forest" or tagi.get("natural") == "wood":
            warstwy.append("las")

    if typ == "punkt" and tagi.get("place") in {"city", "town"} and ludnosc is not None and ludnosc > 50000:
        warstwy.append("miasta_50k")

    if tagi.get("amenity") or tagi.get("shop"):
        warstwy.append("poi")

    return warstwy, ludnosc


def przygotuj_warstwy():
    cel = Path(config.SCIEZKA_WARSTWY_OSM)
    if cel.exists():
        return cel

    cel.parent.mkdir(parents=True, exist_ok=True)
    przelicz = Transformer.from_crs(4326, 2180, always_xy=True).transform
    fabryka = osmium.geom.WKBFactory()
    schemat = pa.schema([("id", pa.string()), ("geometry", pa.binary()), ("x", pa.float64()), ("y", pa.float64()), ("population", pa.float64())])
    liczniki = Counter()

    with TemporaryDirectory(dir=cel.parent) as katalog:
        roboczy = Path(katalog)
        wynik = roboczy / "warstwy"
        wynik.mkdir()
        zapisy = {w: pq.ParquetWriter(wynik / (w + ".parquet"), schemat, compression="zstd") for w in WARSTWY}
        bufory = {w: [] for w in WARSTWY}

        mapa = osmium.FileProcessor(config.SCIEZKA_OSM).with_locations("sparse_file_array," + str(roboczy / "wezly.idx")).with_areas()
        for numer, obiekt in enumerate(mapa, 1):
            if numer % 5000000 == 0:
                print(f"OSM: odczytano {numer:,} obiektów, zapisano {sum(liczniki.values()):,}", flush=True)

            if obiekt.is_relation():
                continue
            tagi = dict(obiekt.tags)
            if not tagi:
                continue
            typ = "obszar" if obiekt.is_area() else "linia" if obiekt.is_way() else "punkt"
            warstwy, ludnosc = wybierz_warstwy(tagi, typ)
            if not warstwy:
                continue

            try:
                if typ == "obszar":
                    geometria = wkb.loads(fabryka.create_multipolygon(obiekt), hex=True)
                    identyfikator = ("w" if obiekt.from_way() else "r") + str(obiekt.orig_id())
                elif typ == "linia":
                    geometria = wkb.loads(fabryka.create_linestring(obiekt), hex=True)
                    identyfikator = "w" + str(obiekt.id)
                else:
                    geometria = wkb.loads(fabryka.create_point(obiekt), hex=True)
                    identyfikator = "n" + str(obiekt.id)
                geometria = transform(przelicz, geometria)
            except (RuntimeError, ValueError):
                continue

            if geometria.is_empty or not geometria.is_valid:
                continue
            srodek = geometria.centroid
            for warstwa in warstwy:
                bufory[warstwa].append({"id": identyfikator, "geometry": geometria.wkb, "x": srodek.x, "y": srodek.y, "population": ludnosc})
                liczniki[warstwa] += 1
                if len(bufory[warstwa]) >= 5000:
                    zapisy[warstwa].write_table(pa.Table.from_pylist(bufory[warstwa], schema=schemat))
                    bufory[warstwa].clear()

        for warstwa in WARSTWY:
            if bufory[warstwa]:
                zapisy[warstwa].write_table(pa.Table.from_pylist(bufory[warstwa], schema=schemat))
            zapisy[warstwa].close()

        wynik.rename(cel)

    return cel
