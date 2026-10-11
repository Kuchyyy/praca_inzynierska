# PostgreSQL i PostGIS w Dockerze

Z katalogu projektu:

```bash
docker compose up -d --build --wait db
docker compose ps db
```

PostgreSQL 17 z PostGIS jest budowany na oficjalnym obrazie
`postgres:17-bookworm`, z pakietami PostGIS z repozytorium PostgreSQL.
Obraz działa natywnie na ARM (Mac Apple Silicon) i amd64.
Źródła: [obraz PostgreSQL](https://hub.docker.com/_/postgres),
[repozytorium pakietów](https://www.postgresql.org/download/linux/debian/).

Hasła są opcjonalne. Bez pliku `.env` nowa baza powstaje bez haseł
(`POSTGRES_HOST_AUTH_METHOD=trust`) i przyjmuje połączenia tylko z tego komputera.
Nikomu nie trzeba przekazywać haseł: każdy uruchamia własną bazę.
Żeby nowa baza wymagała haseł, skopiuj `.env.example` do `.env`, wpisz hasła
i ustaw `POSTGRES_HOST_AUTH_METHOD=scram-sha-256` przed pierwszym startem.
`.env` jest pomijany w Git oraz w kontekście budowania obrazu ETL. Ustawienia
haseł działają tylko przy tworzeniu bazy; istniejąca baza zachowuje swoje.

## Połączenie

| Ustawienie | Wartość |
|---|---|
| Host z komputera | `127.0.0.1` |
| Host z backendu w tym samym Compose | `db` |
| Port z komputera | `POSTGRES_PORT` z `.env`, domyślnie `5432` |
| Port wewnątrz Compose | `5432` |
| Baza | `dzialki` (ustawienie `POSTGRES_DB`) |
| Użytkownik backendu | `dzialki_app` |
| Hasło backendu | `APP_DB_PASSWORD` z `.env`, bez pliku brak hasła |
| Administrator | `POSTGRES_USER`, hasło `POSTGRES_PASSWORD` (opcjonalne) |
| Schemat tabel aplikacji | `dane` |

Port jest dostępny tylko lokalnie. Backend powinien używać `dzialki_app`,
który nie jest superużytkownikiem i nie może tworzyć baz ani ról. Administrator
wykonuje migracje i tworzy tabele w schemacie `dane`; aplikacja automatycznie
otrzymuje do nich prawa odczytu i zapisu. PostGIS jest w schemacie `public`.
Nie utworzono jeszcze tabel domenowych ani nie zaimportowano GeoParquet.

Konsola administratora:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Sprawdzenie PostGIS:

```sql
SELECT version();
SELECT PostGIS_Full_Version();
SELECT ST_Distance(ST_SetSRID(ST_Point(0, 0), 2180),
                   ST_SetSRID(ST_Point(3, 4), 2180));
```

Ostatnie zapytanie powinno zwrócić `5` metrów. Geometrię projektu będziemy
przechowywać w EPSG:2180, z indeksami GiST dodanymi do docelowych tabel.

## Zatrzymanie i dane

```bash
docker compose stop db
docker compose up -d --wait db
```

Dane są w nazwanym wolumenie `postgres_data` projektu Compose, poza obrazem.
Zwykłe `docker compose down` zachowuje dane. Opcja `down -v` usuwa wolumen
wraz z bazą — nie używaj jej do zwykłego restartu.

Inicjalizacja SQL wykonuje się tylko przy pierwszym starcie z pustym
wolumenem. Zmiana hasła w `.env` nie zmienia istniejącego hasła w PostgreSQL;
w istniejącej bazie zmieniamy je przez `\password` w psql, potem w `.env`.

Kopia bazy:

```bash
mkdir -p backend/db/backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "backend/db/backups/dzialki-$(date +%Y%m%d-%H%M%S).dump"
```

ETL jest osobnym profilem i nie startuje razem z bazą:

```bash
docker compose --profile etl run --rm etl
```
