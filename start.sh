#!/bin/bash

set -x  # Enable debug mode to see what's happening

# Check if .env exists, if not create it from example
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo ".env file created"
fi

# Generate new encryption key regardless of existing value
echo "Generating new encryption key..."
NEW_KEY=$(openssl rand -base64 32)
echo "Generated key: $NEW_KEY"

# Remove any existing ENCRYPTION_KEY line and create clean .env
grep -v "^ENCRYPTION_KEY=" .env > .env.tmp
mv .env.tmp .env

# Add the new encryption key at the end of the file
echo "ENCRYPTION_KEY=\"$NEW_KEY\"" >> .env

echo "Updated .env file. Current ENCRYPTION_KEY value:"
grep "^ENCRYPTION_KEY=" .env

# Ask for OpenAI API key
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

# Ask for Mistral API key
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

# Check if "docker compose" is available (Docker Compose v2)
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
# Else, fall back to "docker-compose" (Docker Compose v1)
elif docker-compose --version >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  echo "Neither 'docker compose' nor 'docker-compose' found. Please install Docker Compose."
  exit 1
fi

# Add this block: Check if Docker daemon is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker daemon is not running. Please start Docker and try again."
  exit 1
fi

echo "Using command: $COMPOSE_CMD"

# Check for existing airweave containers
EXISTING_CONTAINERS=$(docker ps -a --filter "name=airweave" --format "{{.Names}}" | tr '\n' ' ')

if [ -n "$EXISTING_CONTAINERS" ]; then
  echo "Found existing airweave containers: $EXISTING_CONTAINERS"
  read -p "Would you like to remove them before starting? (y/n): " REMOVE_CONTAINERS

  if [ "$REMOVE_CONTAINERS" = "y" ] || [ "$REMOVE_CONTAINERS" = "Y" ]; then
    echo "Removing existing containers..."
    docker rm -f $EXISTING_CONTAINERS

    # Also remove the database volume
    echo "Removing database volume..."
    docker volume rm airweave_postgres_data

    echo "Containers and volumes removed."
  else
    echo "Warning: Starting with existing containers may cause conflicts."
  fi
fi

# Now run the appropriate Docker Compose command
$COMPOSE_CMD up -d

echo "Services started! Frontend is available at http://localhost:8080"
