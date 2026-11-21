import re
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

NIE_DROGI = ["footway", "path", "steps", "track", "cycleway", "bridleway", "proposed", "construction", "platform"]
NAWIERZCHNIE_UTWARDZONE = ["asphalt", "concrete", "paving_stones", "sett", "paved", "concrete:plates", "concrete:lanes"]


def wybierz_warstwy(tagi, typ):
    warstwy = []

    ludnosc = re.sub(r"[\s,]", "", tagi.get("population", ""))
    if ludnosc.isdigit():
        ludnosc = int(ludnosc)
    else:
        ludnosc = None

    if typ == "linia":
        droga = tagi.get("highway", "")
        if droga != "" and droga not in NIE_DROGI:
            warstwy.append("drogi")
            if tagi.get("surface") in NAWIERZCHNIE_UTWARDZONE:
                warstwy.append("utwardzone")

    if typ == "obszar":
        budynek = tagi.get("building", "")
        if budynek != "" and budynek != "no":
            warstwy.append("budynki")
        if tagi.get("landuse") == "forest" or tagi.get("natural") == "wood":
            warstwy.append("las")

    if typ == "punkt":
        if tagi.get("place") in ["city", "town"] and ludnosc is not None and ludnosc > 50000:
            warstwy.append("miasta_50k")

    if tagi.get("amenity") or tagi.get("shop"):
        warstwy.append("poi")

    return warstwy, ludnosc


def przygotuj_warstwy():
    cel = Path(config.SCIEZKA_WARSTWY_OSM)
    if cel.exists():
        return cel

    cel.parent.mkdir(parents=True, exist_ok=True)

    na_metry = Transformer.from_crs(4326, 2180, always_xy=True).transform
    fabryka = osmium.geom.WKBFactory()
    schemat = pa.schema([("id", pa.string()), ("geometry", pa.binary()), ("x", pa.float64()), ("y", pa.float64()), ("population", pa.float64())])

    with TemporaryDirectory(dir=cel.parent) as katalog:
        roboczy = Path(katalog) / "warstwy"
        roboczy.mkdir()

        pliki = {}
        bufory = {}
        for warstwa in WARSTWY:
            pliki[warstwa] = pq.ParquetWriter(roboczy / (warstwa + ".parquet"), schemat, compression="zstd")
            bufory[warstwa] = []

        mapa = osmium.FileProcessor(config.SCIEZKA_OSM)
        mapa = mapa.with_locations("sparse_file_array," + str(Path(katalog) / "wezly.idx"))
        mapa = mapa.with_areas()

        for numer, obiekt in enumerate(mapa, 1):
            if numer % 5000000 == 0:
                print(f"OSM: odczytano {numer:,} obiektów", flush=True)

            if obiekt.is_relation():
                continue
            tagi = dict(obiekt.tags)
            if len(tagi) == 0:
                continue

            if obiekt.is_area():
                typ = "obszar"
            elif obiekt.is_way():
                typ = "linia"
            else:
                typ = "punkt"

            warstwy, ludnosc = wybierz_warstwy(tagi, typ)
            if len(warstwy) == 0:
                continue

            try:
                if typ == "obszar":
                    geometria = wkb.loads(fabryka.create_multipolygon(obiekt), hex=True)
                    if obiekt.from_way():
                        identyfikator = "w" + str(obiekt.orig_id())
                    else:
                        identyfikator = "r" + str(obiekt.orig_id())
                elif typ == "linia":
                    geometria = wkb.loads(fabryka.create_linestring(obiekt), hex=True)
                    identyfikator = "w" + str(obiekt.id)
                else:
                    geometria = wkb.loads(fabryka.create_point(obiekt), hex=True)
                    identyfikator = "n" + str(obiekt.id)
                geometria = transform(na_metry, geometria)
            except (RuntimeError, ValueError):
                continue

            if geometria.is_empty or not geometria.is_valid:
                continue

            srodek = geometria.centroid
            for warstwa in warstwy:
                bufory[warstwa].append({"id": identyfikator, "geometry": geometria.wkb, "x": srodek.x, "y": srodek.y, "population": ludnosc})

                if len(bufory[warstwa]) >= 5000:
                    pliki[warstwa].write_table(pa.Table.from_pylist(bufory[warstwa], schema=schemat))
                    bufory[warstwa] = []

        for warstwa in WARSTWY:
            if len(bufory[warstwa]) > 0:
                pliki[warstwa].write_table(pa.Table.from_pylist(bufory[warstwa], schema=schemat))
            pliki[warstwa].close()

        roboczy.rename(cel)

    return cel
