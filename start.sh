#!/bin/bash

set -x  # Enable debug mode to see what's happening
set -euo pipefail

# ---- Optional flags/env (do not change default behavior) ---------------------
NONINTERACTIVE="${NONINTERACTIVE:-}"
SKIP_LOCAL_EMBEDDINGS="${SKIP_LOCAL_EMBEDDINGS:-}"  # Explicitly skip local embeddings
SKIP_FRONTEND="${SKIP_FRONTEND:-}"  # Explicitly skip frontend

while [[ $# -gt 0 ]]; do
  case "$1" in
    --noninteractive) NONINTERACTIVE=1; shift ;;
    --skip-local-embeddings) SKIP_LOCAL_EMBEDDINGS=1; shift ;;
    --skip-frontend) SKIP_FRONTEND=1; shift ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

# ---- Helpers -----------------------------------------------------------------
have_cmd() { command -v "$1" >/dev/null 2>&1; }

# ---- .env handling (backward compatible) -------------------------------------
# Check if .env exists, if not create it from example
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo ".env file created"
fi

# Check if ENCRYPTION_KEY exists AND has a non-empty value in .env
EXISTING_KEY=$(grep "^ENCRYPTION_KEY=" .env 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d ' ')

if [ -n "$EXISTING_KEY" ]; then
    echo "Encryption key already exists in .env file, skipping generation."
    echo "Current ENCRYPTION_KEY value: ********"
else
    echo "No valid encryption key found. Generating new encryption key..."
    NEW_KEY=$(openssl rand -base64 32)
    echo "Generated key: $NEW_KEY"

    # Remove any existing empty ENCRYPTION_KEY line
    grep -v "^ENCRYPTION_KEY=" .env > .env.tmp 2>/dev/null || true
    mv .env.tmp .env

    # Add the new encryption key at the end of the file
    echo "ENCRYPTION_KEY=\"$NEW_KEY\"" >> .env
    echo "Added new ENCRYPTION_KEY to .env file"
fi

# Check if STATE_SECRET exists AND has a non-empty value in .env
EXISTING_STATE_SECRET=$(grep "^STATE_SECRET=" .env 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d ' ')

if [ -n "$EXISTING_STATE_SECRET" ]; then
    echo "STATE_SECRET already exists in .env file, skipping generation."
    echo "Current STATE_SECRET value: ********"
else
    echo "No valid STATE_SECRET found. Generating new HMAC secret..."
    # Generate a secure 32-byte URL-safe secret
    NEW_STATE_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null || openssl rand -base64 32)
    echo "Generated STATE_SECRET: ********"

    # Remove any existing empty STATE_SECRET line
    grep -v "^STATE_SECRET=" .env > .env.tmp 2>/dev/null || true
    mv .env.tmp .env

    # Add the new STATE_SECRET at the end of the file
    echo "STATE_SECRET=\"$NEW_STATE_SECRET\"" >> .env
    echo "Added new STATE_SECRET to .env file"
fi

# Add SKIP_AZURE_STORAGE for faster local startup
if ! grep -q "^SKIP_AZURE_STORAGE=" .env; then
    echo "SKIP_AZURE_STORAGE=true" >> .env
    echo "Added SKIP_AZURE_STORAGE=true for faster startup"
fi

# Ask for OpenAI API key (skip in NONINTERACTIVE)
if [ -z "${NONINTERACTIVE}" ]; then
  echo ""
  echo "OpenAI API key is required for files and natural language search functionality."
  read -p "Would you like to add your OPENAI_API_KEY now? You can also do this later by editing the .env file manually. (y/n): " ADD_OPENAI_KEY

  if [ "$ADD_OPENAI_KEY" = "y" ] || [ "$ADD_OPENAI_KEY" = "Y" ]; then
      read -p "Enter your OpenAI API key: " OPENAI_KEY

      # Remove any existing OPENAI_API_KEY line
      grep -v "^OPENAI_API_KEY=" .env > .env.tmp
      mv .env.tmp .env

      # Add the new OpenAI API key
      echo "OPENAI_API_KEY=\"$OPENAI_KEY\"" >> .env
      echo "OpenAI API key added to .env file."
  else
      echo "You can add your OPENAI_API_KEY later by editing the .env file manually."
      echo "Add the following line to your .env file:"
      echo "OPENAI_API_KEY=\"your-api-key-here\""
  fi
else
  echo "NONINTERACTIVE=1: Skipping OPENAI_API_KEY prompt."
fi

# Ask for Mistral API key (skip in NONINTERACTIVE)
if [ -z "${NONINTERACTIVE}" ]; then
  echo ""
  echo "Mistral API key is required for certain AI functionality."
  read -p "Would you like to add your MISTRAL_API_KEY now? You can also do this later by editing the .env file manually. (y/n): " ADD_MISTRAL_KEY

  if [ "$ADD_MISTRAL_KEY" = "y" ] || [ "$ADD_MISTRAL_KEY" = "Y" ]; then
      read -p "Enter your Mistral API key: " MISTRAL_KEY

      # Remove any existing MISTRAL_API_KEY line
      grep -v "^MISTRAL_API_KEY=" .env > .env.tmp
      mv .env.tmp .env

      # Add the new Mistral API key
      echo "MISTRAL_API_KEY=\"$MISTRAL_KEY\"" >> .env
      echo "Mistral API key added to .env file."
  else
      echo "You can add your MISTRAL_API_KEY later by editing the .env file manually."
      echo "Add the following line to your .env file:"
      echo "MISTRAL_API_KEY=\"your-api-key-here\""
  fi
else
  echo "NONINTERACTIVE=1: Skipping MISTRAL_API_KEY prompt."
fi

# ---- Compose tool selection ---------------------------------------------------
# Check if "docker compose" is available (Docker Compose v2)
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
# Else, fall back to "docker-compose" (Docker Compose v1)
elif docker-compose --version >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
elif podman-compose --version > /dev/null 2>&1; then
  COMPOSE_CMD="podman-compose"
else
  echo "Neither 'docker compose', 'docker-compose', nor 'podman-compose' found. Please install Docker Compose."
  exit 1
fi

# Add this block: Check if Docker daemon is running
if docker info > /dev/null 2>&1; then
    CONTAINER_CMD="docker"
elif have_cmd podman && podman info > /dev/null 2>&1; then
    CONTAINER_CMD="podman"
else
    echo "Error: Docker daemon is not running. Please start Docker and try again."
    exit 1
fi

echo "Using commands: ${CONTAINER_CMD} and ${COMPOSE_CMD}"

# Check for existing airweave containers
EXISTING_CONTAINERS=$(${CONTAINER_CMD} ps -a --filter "name=airweave" --format "{{.Names}}" | tr '\n' ' ')

if [ -n "$EXISTING_CONTAINERS" ]; then
  echo "Found existing airweave containers: $EXISTING_CONTAINERS"
  if [ -z "${NONINTERACTIVE}" ]; then
    read -p "Would you like to remove them before starting? (y/n): " REMOVE_CONTAINERS
    if [ "$REMOVE_CONTAINERS" = "y" ] || [ "$REMOVE_CONTAINERS" = "Y" ]; then
      echo "Removing existing containers..."
      ${CONTAINER_CMD} rm -f $EXISTING_CONTAINERS || true
      echo "Removing database volume..."
      ${CONTAINER_CMD} volume rm airweave_postgres_data || true
      echo "Containers and volumes removed."
    else
      echo "Warning: Starting with existing containers may cause conflicts."
    fi
  else
    echo "NONINTERACTIVE=1: Removing existing containers and volume..."
    ${CONTAINER_CMD} rm -f $EXISTING_CONTAINERS || true
    ${CONTAINER_CMD} volume rm airweave_postgres_data || true
  fi
fi

echo ""

# Show which images will be used
if [ -n "${BACKEND_IMAGE:-}" ] || [ -n "${FRONTEND_IMAGE:-}" ]; then
    echo "Using custom Docker images:"
    echo "  Backend:  ${BACKEND_IMAGE:-ghcr.io/airweave-ai/airweave-backend:latest}"
    echo "  Frontend: ${FRONTEND_IMAGE:-ghcr.io/airweave-ai/airweave-frontend:latest}"
    echo ""
fi

# Determine which optional services to start (default: all enabled for local dev)
USE_LOCAL_EMBEDDINGS=true
USE_FRONTEND=true

# Check if OpenAI API key exists in .env - auto-skip local embeddings if present
if [ -f .env ]; then
    OPENAI_KEY=$(grep "^OPENAI_API_KEY=" .env 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d ' ')
    if [ -n "$OPENAI_KEY" ] && [ "$OPENAI_KEY" != "your-api-key-here" ]; then
        echo "OpenAI API key detected - skipping local embeddings service (~2GB)"
        USE_LOCAL_EMBEDDINGS=false
    fi
fi

# Check for explicit skip flags (used in CI)
if [ -n "$SKIP_LOCAL_EMBEDDINGS" ]; then
    echo "SKIP_LOCAL_EMBEDDINGS is set - skipping local embeddings service"
    USE_LOCAL_EMBEDDINGS=false
fi

if [ -n "$SKIP_FRONTEND" ]; then
    echo "SKIP_FRONTEND is set - skipping frontend service"
    USE_FRONTEND=false
fi

# Build compose command with profiles (default: enable both)
COMPOSE_CMD_WITH_OPTS="$COMPOSE_CMD -f docker/docker-compose.yml"
if [ "$USE_LOCAL_EMBEDDINGS" = true ]; then
    echo "Starting with local embeddings service (text2vec-transformers)"
    COMPOSE_CMD_WITH_OPTS="$COMPOSE_CMD_WITH_OPTS --profile local-embeddings"
else
    echo "Starting without local embeddings (backend will use OpenAI)"
fi

if [ "$USE_FRONTEND" = true ]; then
    echo "Starting with frontend UI"
    COMPOSE_CMD_WITH_OPTS="$COMPOSE_CMD_WITH_OPTS --profile frontend"
else
    echo "Starting without frontend (backend-only mode)"
fi

echo "Starting Docker services..."
if ! $COMPOSE_CMD_WITH_OPTS up -d; then
    echo "❌ Failed to start Docker services"
    echo "Check the error messages above and try running:"
    echo "  docker logs airweave-backend"
    echo "  docker logs airweave-frontend"
    exit 1
fi

# Wait a moment for services to initialize
echo ""
echo "Waiting for services to initialize..."
sleep 10

# Check if Vespa document API is ready (wait for vespa-init to complete)
echo "Checking Vespa readiness..."
MAX_VESPA_RETRIES=60
VESPA_RETRY_COUNT=0
VESPA_READY=false

while [ $VESPA_RETRY_COUNT -lt $MAX_VESPA_RETRIES ]; do
  # Check if vespa-init has completed (exited with status 0)
  INIT_STATUS=$(${CONTAINER_CMD} inspect airweave-vespa-init --format='{{.State.Status}}' 2>/dev/null || echo "not_found")
  INIT_EXIT_CODE=$(${CONTAINER_CMD} inspect airweave-vespa-init --format='{{.State.ExitCode}}' 2>/dev/null || echo "1")

  if [ "$INIT_STATUS" = "exited" ] && [ "$INIT_EXIT_CODE" = "0" ]; then
    # Init completed, now verify document API is actually ready for requests
    # Use timeout and write to temp file to avoid concatenation issues
    if timeout 5 curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/document/v1/ > /tmp/vespa_status_$$ 2>&1; then
      DOC_STATUS=$(cat /tmp/vespa_status_$$ 2>/dev/null | tr -cd '0-9' || echo "000")
      rm -f /tmp/vespa_status_$$
      
      # Any HTTP response code (400, 404, 200, etc.) means API is responding
      # Only "000" or empty means connection failed
      if [ -n "$DOC_STATUS" ] && [ "$DOC_STATUS" != "000" ] && [ "$DOC_STATUS" -ge 100 ] 2>/dev/null; then
        echo "✅ Vespa is ready! (init completed, document API verified: HTTP $DOC_STATUS)"
        VESPA_READY=true
        break
      else
        echo "⏳ Vespa init done but document API not responding (attempt $((VESPA_RETRY_COUNT + 1))/$MAX_VESPA_RETRIES)"
      fi
    else
      rm -f /tmp/vespa_status_$$
      echo "⏳ Vespa document API not reachable (attempt $((VESPA_RETRY_COUNT + 1))/$MAX_VESPA_RETRIES)"
    fi
  elif [ "$INIT_STATUS" = "exited" ] && [ "$INIT_EXIT_CODE" != "0" ]; then
    echo "❌ Vespa init container failed with exit code $INIT_EXIT_CODE"
    echo "Check vespa-init logs with: ${CONTAINER_CMD} logs airweave-vespa-init"
    break
  else
    echo "⏳ Waiting for Vespa init... (attempt $((VESPA_RETRY_COUNT + 1))/$MAX_VESPA_RETRIES, init_status=$INIT_STATUS)"
  fi

  VESPA_RETRY_COUNT=$((VESPA_RETRY_COUNT + 1))
  sleep 5
done

if [ "$VESPA_READY" = false ]; then
  echo "❌ Vespa not ready after $((MAX_VESPA_RETRIES * 5)) seconds"
  echo "Check vespa logs: ${CONTAINER_CMD} logs airweave-vespa"
  echo "Check vespa-init logs: ${CONTAINER_CMD} logs airweave-vespa-init"
  echo ""
  echo "Vespa troubleshooting:"
  echo "  1. Check if Vespa container is running: ${CONTAINER_CMD} ps | grep vespa"
  echo "  2. Check Vespa health: curl http://localhost:8081/state/v1/health"
  echo "  3. Check document API: curl http://localhost:8081/document/v1/"
  exit 1
fi

# Check if backend is healthy (with retries)
echo "Checking backend health..."
MAX_RETRIES=30
RETRY_COUNT=0
BACKEND_HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if ${CONTAINER_CMD} exec airweave-backend curl -f http://localhost:8001/health >/dev/null 2>&1; then
    echo "✅ Backend is healthy!"
    BACKEND_HEALTHY=true
    break
  else
    echo "⏳ Backend is still starting... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 5
  fi
done

if [ "$BACKEND_HEALTHY" = false ]; then
  echo "❌ Backend failed to start after $MAX_RETRIES attempts"
  echo "Check backend logs with: docker logs airweave-backend"
  echo "Common issues:"
  echo "  - Database connection problems"
  echo "  - Missing environment variables"
  echo "  - Platform sync errors"
fi

# Check if frontend needs to be started manually (only if we started it)
if [ "$USE_FRONTEND" = true ]; then
  FRONTEND_STATUS=$(${CONTAINER_CMD} inspect airweave-frontend --format='{{.State.Status}}' 2>/dev/null || true)
  if [ "$FRONTEND_STATUS" = "created" ] || [ "$FRONTEND_STATUS" = "exited" ]; then
    echo "Starting frontend container..."
    ${CONTAINER_CMD} start airweave-frontend || true
    sleep 5
  fi
fi

# Final status check
echo ""
echo "🚀 Airweave Status:"
echo "=================="

SERVICES_HEALTHY=true

# Check each service
if ${CONTAINER_CMD} exec airweave-backend curl -f http://localhost:8001/health >/dev/null 2>&1; then
  echo "✅ Backend API:    http://localhost:8001"
else
  echo "❌ Backend API:    Not responding (check logs with: docker logs airweave-backend)"
  SERVICES_HEALTHY=false
fi

# Only check frontend if we started it
if [ "$USE_FRONTEND" = true ]; then
  if curl -f http://localhost:8080 >/dev/null 2>&1; then
    echo "✅ Frontend UI:    http://localhost:8080"
  else
    echo "❌ Frontend UI:    Not responding (check logs with: docker logs airweave-frontend)"
    SERVICES_HEALTHY=false
  fi
else
  echo "⏭️  Frontend UI:    Skipped (backend-only mode)"
fi

echo ""
echo "Other services:"
echo "📊 Temporal UI:    http://localhost:8088"
echo "🗄️  PostgreSQL:    localhost:5432"
echo "🔍 Qdrant:         http://localhost:6333"
if curl -sf http://localhost:8081/state/v1/health | grep -q '"up"' 2>/dev/null; then
  echo "🔎 Vespa:          http://localhost:8081"
else
  echo "⚠️  Vespa:          Not responding (check logs with: docker logs airweave-vespa)"
fi

if [ "$USE_LOCAL_EMBEDDINGS" = true ]; then
  echo "🤖 Embeddings:    http://localhost:9878 (local text2vec)"
else
  echo "🤖 Embeddings:    OpenAI API"
fi
echo ""
echo "To view logs: docker logs <container-name>"
echo "To stop all services: docker compose -f docker/docker-compose.yml down"
echo ""

if [ "$SERVICES_HEALTHY" = true ]; then
  echo "🎉 All services started successfully!"
else
  echo "⚠️  Some services failed to start properly. Check the logs above for details."
  exit 1
fi
