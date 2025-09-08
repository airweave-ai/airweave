#!/bin/bash

set -x  # Enable debug mode to see what's happening
set -euo pipefail

# ---- Optional flags/env (do not change default behavior) ---------------------
NONINTERACTIVE="${NONINTERACTIVE:-}"
CI_COMPOSE_OVERRIDE="${CI_COMPOSE_OVERRIDE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --noninteractive) NONINTERACTIVE=1; shift ;;
    --compose-override) CI_COMPOSE_OVERRIDE="$2"; shift 2 ;;
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

# Now run the appropriate Docker Compose command with optional override
COMPOSE_FILES="-f docker/docker-compose.yml"
if [ -n "${CI_COMPOSE_OVERRIDE:-}" ] && [ -f "$CI_COMPOSE_OVERRIDE" ]; then
  COMPOSE_FILES="$COMPOSE_FILES -f $CI_COMPOSE_OVERRIDE"
fi

echo ""

# Show which images will be used
if [ -n "${BACKEND_IMAGE:-}" ] || [ -n "${FRONTEND_IMAGE:-}" ]; then
    echo "Using custom Docker images:"
    echo "  Backend:  ${BACKEND_IMAGE:-ghcr.io/airweave-ai/airweave-backend:latest}"
    echo "  Frontend: ${FRONTEND_IMAGE:-ghcr.io/airweave-ai/airweave-frontend:latest}"
    echo ""
fi

echo "Starting Docker services..."
if ! $COMPOSE_CMD $COMPOSE_FILES up -d; then
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

# Check if frontend needs to be started manually
FRONTEND_STATUS=$(${CONTAINER_CMD} inspect airweave-frontend --format='{{.State.Status}}' 2>/dev/null || true)
if [ "$FRONTEND_STATUS" = "created" ] || [ "$FRONTEND_STATUS" = "exited" ]; then
  echo "Starting frontend container..."
  ${CONTAINER_CMD} start airweave-frontend || true
  sleep 5
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

if curl -f http://localhost:8080 >/dev/null 2>&1; then
  echo "✅ Frontend UI:    http://localhost:8080"
else
  echo "❌ Frontend UI:    Not responding (check logs with: docker logs airweave-frontend)"
  SERVICES_HEALTHY=false
fi

echo ""
echo "Other services:"
echo "📊 Temporal UI:    http://localhost:8088"
echo "🗄️  PostgreSQL:    localhost:5432"
echo "🔍 Qdrant:        http://localhost:6333"
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
