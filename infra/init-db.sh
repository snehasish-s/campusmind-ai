#!/bin/sh
set -eu
# App role owns only its application schema and cannot create databases or roles.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=app_password="$APP_DB_PASSWORD" <<'EOSQL'
CREATE ROLE campusmind_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE campusmind TO campusmind_app;
GRANT USAGE, CREATE ON SCHEMA public TO campusmind_app;
EOSQL
