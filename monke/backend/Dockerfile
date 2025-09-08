# monke/backend/Dockerfile
FROM python:3.12-slim

# Make /app the import root so "import monke" resolves to /app/monke
WORKDIR /app

# Build essentials (only what's needed) and clean up apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt lives at the build context root (monke/requirements.txt)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the whole monke repo (build context is monke/) into /app/monke
COPY . /app/monke

EXPOSE 8081

# Ensure clean logs and correct import path
ENV PYTHONUNBUFFERED=1
# (Strictly optional because WORKDIR=/app already works; kept for clarity)
ENV PYTHONPATH=/app

# Keep your existing app import path
CMD ["uvicorn", "monke.backend.app:app", "--host", "0.0.0.0", "--port", "8081"]
