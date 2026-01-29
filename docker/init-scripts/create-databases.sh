#!/bin/bash
# Creates the svix database for webhook delivery
# This script runs automatically when Postgres initializes (first start only)

set -e

echo "Creating svix database..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE svix'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'svix')\gexec
EOSQL

echo "✓ Svix database created successfully!"
