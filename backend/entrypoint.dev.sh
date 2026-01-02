#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
poetry run python -c "
from tenacity import retry, stop_after_attempt, wait_fixed
from sqlalchemy import create_engine
import os

@retry(stop=stop_after_attempt(5), wait=wait_fixed(2))
def check_db():
    user = os.getenv('POSTGRES_USER', 'airweave')
    password = os.getenv('POSTGRES_PASSWORD', 'airweave1234!')
    host = os.getenv('POSTGRES_HOST', 'db')
    db = os.getenv('POSTGRES_DB', 'airweave')
    port = os.getenv('POSTGRES_PORT', '5432')
    engine = create_engine(f'postgresql://{user}:{password}@{host}/{db}')
    engine.connect()

check_db()
"

# Run migrations using our existing Alembic setup
echo "Running database migrations..."
cd /app && poetry run alembic upgrade head
# cd /app #dev time to not rerun alembic on conflicting branches

# Start application with hot reloading enabled
echo "Starting application with hot reloading..."
poetry run uvicorn airweave.main:app --host 0.0.0.0 --port 8001 --reload --reload-dir /app/airweave --reload-exclude "local_storage/*"
