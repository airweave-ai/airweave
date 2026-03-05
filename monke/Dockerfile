FROM python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c as backend
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl git && rm -rf /var/lib/apt/lists/*
COPY monke/requirements.txt /app/monke/requirements.txt
RUN pip install --no-cache-dir -r /app/monke/requirements.txt
COPY monke /app/monke

# Frontend build stage
FROM node:20.20.0-slim@sha256:d8a35d586fad3af7abb6fdb9ba972388395405f4d462da9e4a4ddcde67b5e0fb as frontend
WORKDIR /ui
COPY monke/frontend/package.json monke/frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY monke/frontend ./
# Copy icons from main Airweave frontend
COPY frontend/src/components/icons/apps ./public/icons
RUN npm run build

# Final image
FROM python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=backend /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=backend /usr/local/bin /usr/local/bin
COPY --from=backend /app/monke /app/monke
COPY --from=frontend /ui/dist /app/monke/frontend_dist

EXPOSE 8081
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "uvicorn", "monke.backend.app:app", "--host", "0.0.0.0", "--port", "8081"]
