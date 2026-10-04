import json
import re
import shutil
import time
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


WARSTWY = [
    "budynki", "mieszkalne", "zabudowa", "las", "woda", "rzeki", "granica",
    "drogi", "utwardzone", "glowne", "lokalne", "autostrady",
    "wezly", "przystanki", "miejscowosci", "miasta", "miasta_10k", "miasta_50k",
    "wroclaw", "szkoly", "sklepy", "przedszkola", "poi",
]


def wybierz_warstwy(tagi, typ):
    warstwy = []
    droga = tagi.get("highway", "")
    budynek = tagi.get("building", "")
    miejsce = tagi.get("place", "")
    ludnosc = re.sub(r"[\s,]", "", tagi.get("population", ""))
    ludnosc = int(ludnosc) if ludnosc.isdigit() else None

    if typ == "linia":
        wykluczone = {"footway", "path", "steps", "track", "cycleway", "bridleway", "proposed", "construction", "platform"}
        if droga and droga not in wykluczone:
            warstwy.append("drogi")
            if tagi.get("surface") in {"asphalt", "concrete", "paving_stones", "sett", "paved", "concrete:plates", "concrete:lanes"}:
                warstwy.append("utwardzone")
        if droga in {"primary", "trunk", "primary_link", "trunk_link"}:
            warstwy.append("glowne")
        if droga == "residential":
            warstwy.append("lokalne")
        if droga == "motorway":
            warstwy.append("autostrady")
        if tagi.get("waterway") == "river":
            warstwy.append("rzeki")
        return warstwy, ludnosc

    if typ == "obszar":
        if budynek and budynek != "no":
            warstwy.append("budynki")
        if budynek in {"house", "residential", "apartments", "detached"}:
            warstwy.append("mieszkalne")
        if tagi.get("landuse") == "residential":
            warstwy.append("zabudowa")
        if tagi.get("landuse") == "forest" or tagi.get("natural") == "wood":
            warstwy.append("las")
        if tagi.get("natural") == "water":
            warstwy.append("woda")
        if tagi.get("boundary") == "administrative" and tagi.get("admin_level") == "2" and tagi.get("ISO3166-1") == "PL":
            warstwy.append("granica")

    if typ == "punkt":
        if droga == "motorway_junction":
            warstwy.append("wezly")
        if droga == "bus_stop":
            warstwy.append("przystanki")
        if miejsce in {"city", "town", "village"}:
            warstwy.append("miejscowosci")
        if miejsce in {"city", "town"}:
            warstwy.append("miasta")
            if ludnosc is not None and ludnosc > 10000:
                warstwy.append("miasta_10k")
            if ludnosc is not None and ludnosc > 50000:
                warstwy.append("miasta_50k")
        if miejsce == "city" and tagi.get("name") == "Wrocław":
            warstwy.append("wroclaw")

    if tagi.get("amenity") == "school":
        warstwy.append("szkoly")
    if tagi.get("amenity") == "kindergarten":
        warstwy.append("przedszkola")
    if tagi.get("shop") in {"supermarket", "convenience"}:
        warstwy.append("sklepy")
    if tagi.get("amenity") or tagi.get("shop"):
        warstwy.append("poi")

    return warstwy, ludnosc


def przygotuj_warstwy():
    zrodlo = Path(config.SCIEZKA_OSM)
    cel = Path(config.SCIEZKA_WARSTWY_OSM)
    podpis = {"plik": str(zrodlo.resolve()), "bajty": zrodlo.stat().st_size, "mtime_ns": zrodlo.stat().st_mtime_ns, "wersja": 1}
    if cel.exists():
        opis = json.loads((cel / "opis.json").read_text())
        if opis["zrodlo"] != podpis:
            raise ValueError("Zmienione zrodlo OSM; ustaw nowy katalog warstw")
        return cel

    cel.parent.mkdir(parents=True, exist_ok=True)
    przelicz = Transformer.from_crs(4326, 2180, always_xy=True).transform
    fabryka = osmium.geom.WKBFactory()
    schemat = pa.schema([("id", pa.string()), ("geometry", pa.binary()), ("x", pa.float64()), ("y", pa.float64()), ("population", pa.float64())])
    liczniki = Counter()
    bledy = Counter()
    start = time.monotonic()
    postep = Path(config.SCIEZKA_POSREDNIE) / "osm_postep.json"

    with TemporaryDirectory(prefix=".osm-", dir=cel.parent) as katalog:
        roboczy = Path(katalog)
        wynik = roboczy / "warstwy"
        wynik.mkdir()
        zapisy = {w: pq.ParquetWriter(wynik / (w + ".parquet"), schemat, compression="zstd") for w in WARSTWY}
        bufory = {w: [] for w in WARSTWY}
        try:
            mapa = osmium.FileProcessor(zrodlo).with_locations("sparse_file_array," + str(roboczy / "wezly.idx")).with_areas()
            for numer, obiekt in enumerate(mapa, 1):
                if numer % 100000 == 0:
                    if shutil.disk_usage(roboczy).free < (config.ZAPAS_DYSKU_GIB + 1) * 1024**3:
                        raise RuntimeError("Malo miejsca podczas odczytu OSM")
                    stan = {"status": "odczyt_osm", "obiekty": numer, "warstwy": dict(liczniki), "czas_sekundy": round(time.monotonic()-start)}
                    postep.write_text(json.dumps(stan, indent=2))
                    if numer % 5000000 == 0:
                        print(f"OSM: odczytano {numer:,} obiektow, zapisano {sum(liczniki.values()):,}", flush=True)

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
                except (RuntimeError, ValueError) as blad:
                    bledy[typ] += 1
                    continue

                if geometria.is_empty or not geometria.is_valid:
                    bledy[typ] += 1
                    continue
                srodek = geometria.centroid
                for warstwa in warstwy:
                    ksztalt = geometria.boundary if warstwa == "granica" else geometria
                    bufory[warstwa].append({"id": identyfikator, "geometry": ksztalt.wkb, "x": srodek.x, "y": srodek.y, "population": ludnosc})
                    liczniki[warstwa] += 1
                    if len(bufory[warstwa]) >= 5000:
                        zapisy[warstwa].write_table(pa.Table.from_pylist(bufory[warstwa], schema=schemat))
                        bufory[warstwa].clear()

            for warstwa in WARSTWY:
                if bufory[warstwa]:
                    zapisy[warstwa].write_table(pa.Table.from_pylist(bufory[warstwa], schema=schemat))
        finally:
            for zapis in zapisy.values():
                zapis.close()

        opis = {"zrodlo": podpis, "crs": "EPSG:2180", "liczniki": dict(liczniki), "pominiete_bledne_geometrie": dict(bledy), "czas_sekundy": round(time.monotonic()-start)}
        (wynik / "opis.json").write_text(json.dumps(opis, indent=2))
        wynik.rename(cel)

    return cel
