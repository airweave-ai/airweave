FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and poetry in one optimized layer
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unixodbc \
    unixodbc-dev \
    exiftool \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && pip install --no-cache-dir poetry==1.8.4

# Configure poetry for Docker environment
RUN poetry config virtualenvs.create false \
    && poetry config virtualenvs.in-project false \
    && poetry config cache-dir /opt/poetry-cache

# Copy poetry files first for better layer caching
COPY pyproject.toml poetry.lock ./

# Install dependencies with cache mount
RUN --mount=type=cache,target=/opt/poetry-cache \
    poetry install --only=main --no-interaction --no-ansi --no-root

# Copy entrypoint script with proper permissions
COPY --chmod=755 entrypoint.sh /app/entrypoint.sh

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/root/.local/bin:$PATH"

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
