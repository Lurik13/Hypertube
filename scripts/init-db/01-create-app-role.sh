#!/bin/sh
# Runs once, when the pgdata volume is empty (official postgres image behaviour).
# Creates the non-superuser role the backend connects with, makes it owner of
# the app database (so it owns the public schema and can run migrations), and
# creates the separate test database used by `make test`.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v app_user="$APP_DB_USER" -v app_password="$APP_DB_PASSWORD" -v app_db="$POSTGRES_DB" <<'SQL'
SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
    :'app_user', :'app_password'
) \gexec

SELECT format('ALTER DATABASE %I OWNER TO %I', :'app_db', :'app_user') \gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'app_db' || '_test', :'app_user') \gexec
SQL
