-- Create a restricted runtime role. The official image executes this file
-- only when initializing an empty PostgreSQL data directory.
\getenv app_user TM_DB_USER
\getenv app_password TM_DB_PASSWORD

SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
    :'app_user',
    :'app_password'
) \gexec

SELECT format(
    'GRANT CONNECT, TEMPORARY, CREATE ON DATABASE %I TO %I',
    current_database(),
    :'app_user'
) \gexec

SELECT format(
    'GRANT USAGE, CREATE ON SCHEMA public TO %I',
    :'app_user'
) \gexec
