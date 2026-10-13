# Dane i baza PostgreSQL/PostGIS

Tu są źródła, wyniki obliczeń i konfiguracja bazy w Dockerze.
Dane są lokalne, pomijane w Git i w obrazie Dockera.

```text
dane/
  surowe/rcn/     transakcje działek z RCN (GeoParquet)
  surowe/osm/     mapa OSM Polski (PBF)
  posrednie/      cache granic ULDK/EGiB i warstwy OSM
  gotowe/         wyniki kolejnych etapów i model.joblib
```

Źródła pobiera pierwszy etap `python main.py` (`db/pobierz_dane.py`):

| Plik | Źródło |
|---|---|
| `0_transakcje_ceny_dzialki.parquet` | [GUGiK, eksport RCN dla działek](https://github.com/GlownyUrzadGeodezjiIKartografii/pobierz_dane_GUGiK/blob/main/pobierz_dane_GUGiK_dockwidget.py) (14 795 036 wierszy, stan z 02.10.2026) |
| `poland-260930.osm.pbf` | [Geofabrik](https://download.geofabrik.de/europe/poland.html), stan z 30.09.2026 |

Przy dalszym wykorzystaniu danych należy zachować informację o źródle
i oznaczenie autorów OpenStreetMap.

Import do bazy (`db/import_postgis.py`) tworzy w schemacie `dane` tabelę `transakcje`
i 6 tabel `osm_*` (budynki, drogi, utwardzone, las, poi, miasta_50k) z indeksami GiST. Każda tabela importuje się w jednej transakcji,
więc przerwany import nie zostawia połowy tabeli. Uruchomienie bazy i połączenie:
[POSTGIS.md](POSTGIS.md).
