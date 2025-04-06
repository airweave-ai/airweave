#!/bin/bash
set -e  # Exit on error

echo "🌿 Generating Airweave API documentation..."

# Check if we're in the fern directory
if [[ $(basename "$PWD") != "fern" ]]; then
    echo "❌ Please run this script from the fern directory"
    exit 1
fi

# Generate OpenAPI spec
echo "📝 Generating OpenAPI spec..."
cd ../backend
poetry run python ../.github/scripts/generate_openapi.py
cd ../fern

# Ensure directories exist
mkdir -p openapi
mkdir -p definition

# Copy OpenAPI spec to Fern location
echo "📋 Copying OpenAPI spec to Fern..."
cp openapi/openapi.json definition/openapi.json

# Check if fern CLI is installed
if ! command -v fern &> /dev/null; then
    echo "🔧 Installing Fern CLI..."
    npm install -g fern-api
fi

# Generate Fern docs
echo "📚 Generating Fern documentation..."
if [ -z "$FERN_TOKEN" ]; then
    echo "⚠️  Warning: FERN_TOKEN not set. Some features might not work."
fi

echo "🚀 Running Fern generators..."
fern generate --group public --log-level debug

echo "✅ Done! Generated files:"
ls -la definition/


# Generate docs
echo "📚 Generating Fern documentation..."
fern generate --docs
