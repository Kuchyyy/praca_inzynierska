\set ON_ERROR_STOP on
\getenv app_password APP_DB_PASSWORD
\getenv database POSTGRES_DB
\getenv administrator POSTGRES_USER

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE ROLE dzialki_app LOGIN PASSWORD :'app_password';
REVOKE ALL ON DATABASE :"database" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"database" TO dzialki_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO dzialki_app;

CREATE SCHEMA dane AUTHORIZATION :"administrator";
GRANT USAGE ON SCHEMA dane TO dzialki_app;
ALTER DEFAULT PRIVILEGES FOR ROLE :"administrator" IN SCHEMA dane
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dzialki_app;
ALTER DEFAULT PRIVILEGES FOR ROLE :"administrator" IN SCHEMA dane
    GRANT USAGE, SELECT ON SEQUENCES TO dzialki_app;
ALTER ROLE dzialki_app IN DATABASE :"database" SET search_path = dane, public;
