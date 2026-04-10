-- Motis Postgres Init Script
-- Runs once on first container boot (docker-entrypoint-initdb.d).

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";    -- gen_random_uuid() fallback
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- trigram similarity for fuzzy search
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"; -- query performance tracking

-- Create test DB for CI (mirrors main DB structure)
CREATE DATABASE motis_test
    WITH
    OWNER = motis
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    TEMPLATE = template0;

\c motis_test
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
