from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from psycopg import sql

import config
from wycena.baza import polacz


def typ_kolumny(pole):
    if pole.name == "geometry":
        return "geometry(Geometry,2180) NOT NULL"
    if pa.types.is_string(pole.type):
        return "text"
    if pa.types.is_boolean(pole.type):
        return "boolean"
    if pa.types.is_integer(pole.type):
        return "bigint"
    if pa.types.is_floating(pole.type):
        return "double precision"
    if pa.types.is_timestamp(pole.type):
        return "timestamp without time zone"
    raise ValueError(f"Nieobsługiwany typ kolumny: {pole}")


def importuj_plik(baza, plik, nazwa):
    if baza.execute("SELECT to_regclass(%s)", ("dane." + nazwa,)).fetchone()[0]:
        print(f"{nazwa}: już jest w bazie")
        return

    parquet = pq.ParquetFile(plik)
    tabela = sql.Identifier("dane", nazwa)
    kolumny = []
    for pole in parquet.schema_arrow:
        kolumny.append(sql.SQL("{} {}").format(sql.Identifier(pole.name), sql.SQL(typ_kolumny(pole))))
    kopiowanie = sql.SQL("COPY {} ({}) FROM STDIN").format(
        tabela, sql.SQL(", ").join(sql.Identifier(n) for n in parquet.schema_arrow.names)
    )

    # Cały import jednej tabeli w transakcji: po przerwaniu tabela nie zostaje w połowie.
    with baza.transaction():
        baza.execute(sql.SQL("CREATE TABLE {} ({})").format(tabela, sql.SQL(", ").join(kolumny)))

        wykonane = 0
        for partia in parquet.iter_batches(batch_size=config.WIELKOSC_PARTII):
            wartosci = []
            for pole, kolumna in zip(parquet.schema_arrow, partia.columns):
                if pole.name == "geometry":
                    geometrie = shapely.set_srid(shapely.from_wkb(kolumna.to_numpy(zero_copy_only=False)), 2180)
                    wartosci.append(shapely.to_wkb(geometrie, hex=True, include_srid=True))
                else:
                    wartosci.append(kolumna.to_pylist())

            with baza.cursor().copy(kopiowanie) as zapis:
                for rekord in zip(*wartosci):
                    zapis.write_row(rekord)
            wykonane += partia.num_rows
            print(f"{nazwa}: {wykonane:,}/{parquet.metadata.num_rows:,}", flush=True)

        if nazwa == "transakcje":
            baza.execute(sql.SQL("ALTER TABLE {} ADD PRIMARY KEY (klucz_transakcji)").format(tabela))
            baza.execute(sql.SQL(
                "ALTER TABLE {} ADD COLUMN srodek geometry(Point,2180) "
                "GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(x_2180, y_2180), 2180)) STORED"
            ).format(tabela))
            for indeks in ["USING gist (srodek)", "(dok_data)", "(dzi_id_dzialki)", "(teryt_gmina, dok_data)", "(teryt_obreb, dok_data)"]:
                baza.execute(sql.SQL("CREATE INDEX ON {} " + indeks).format(tabela))
        baza.execute(sql.SQL("CREATE INDEX ON {} USING gist (geometry)").format(tabela))

    baza.execute(sql.SQL("ANALYZE {}").format(tabela))
    print(f"{nazwa}: gotowe")


def importuj_dane():
    pliki = [(Path(config.SCIEZKA_PELNE_CECHY), "transakcje")]
    for plik in sorted(Path(config.SCIEZKA_WARSTWY_OSM).glob("*.parquet")):
        pliki.append((plik, "osm_" + plik.stem))

    with polacz(administrator=True) as baza:
        for plik, nazwa in pliki:
            importuj_plik(baza, plik, nazwa)


if __name__ == "__main__":
    importuj_dane()
