FROM python:3.13.12-slim@sha256:8bc60ca09afaa8ea0d6d1220bde073bacfedd66a4bf8129cbdc8ef0e16c8a952

# Set working directory
WORKDIR /app

# Install system dependencies and poetry
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    unixodbc \
    unixodbc-dev \
    exiftool \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir poetry==1.8.4

# Add Poetry to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy poetry files from current directory (backend)
COPY pyproject.toml poetry.lock ./

# Configure poetry
RUN poetry config virtualenvs.create false

# Install dependencies only (no root project)
RUN poetry install --no-interaction --no-ansi --no-root

# Copy the entire backend code (worker needs access to all modules)
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 worker && chown -R worker:worker /app
USER worker

# Set Python path
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the Temporal worker
CMD ["python", "-m", "airweave.platform.temporal.worker"]
