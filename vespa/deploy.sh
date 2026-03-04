#!/bin/bash
set -euo pipefail

# Deploy Vespa application package to config server
# Usage: ./deploy.sh
#
# Reads EMBEDDING_DIMENSIONS from .env to configure schema dimensions.
# Default: 1536 (OpenAI text-embedding-3-small)

CONFIG_SERVER="http://localhost:19071"
SCRIPT_DIR="$(dirname "$0")"
APP_DIR="${SCRIPT_DIR}/app"
BUILD_DIR="${SCRIPT_DIR}/build"

# Source .env from project root if it exists
ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "${ENV_FILE}" ]; then
    echo "Loading configuration from .env..."
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
fi

# Get embedding dimensions (default: 1536 for OpenAI)
EMBEDDING_DIM="${EMBEDDING_DIMENSIONS:-1536}"
echo "Using EMBEDDING_DIMENSIONS=${EMBEDDING_DIM}"

echo ""
echo "Waiting for config server to be ready..."
until curl -s "${CONFIG_SERVER}/state/v1/health" | grep -q '"up"'; do
    echo "  Config server not ready, waiting..."
    sleep 5
done
echo "Config server is ready!"

echo ""
echo "Templating schema files with EMBEDDING_DIM=${EMBEDDING_DIM}..."
rm -rf "${BUILD_DIR}"
cp -r "${APP_DIR}" "${BUILD_DIR}"

# Replace {{EMBEDDING_DIM}} placeholder in all schema files
find "${BUILD_DIR}/schemas" -name "*.sd" -exec sed -i '' "s/{{EMBEDDING_DIM}}/${EMBEDDING_DIM}/g" {} \;

echo ""
echo "Creating application package zip..."
cd "${BUILD_DIR}"
rm -f ../app.zip
zip -r ../app.zip . -x ".*"
cd ..

echo ""
echo "Deploying application package..."
curl -s --header "Content-Type:application/zip" \
    --data-binary @app.zip \
    "${CONFIG_SERVER}/application/v2/tenant/default/prepareandactivate" | jq .

echo ""
echo "Deployment complete!"
echo ""
echo "Waiting for application to be ready..."
sleep 10

echo ""
echo "Checking cluster status..."
curl -s "${CONFIG_SERVER}/application/v2/tenant/default/application/default/environment/prod/region/default/instance/default/serviceconverge" | jq .

echo ""
echo "=== Test Instructions ==="
echo ""
echo "1. Check config server logs (should show only configserver, no services):"
echo "   docker logs vespa-config 2>&1 | grep -E 'Starting|sentinel'"
echo ""
echo "2. Check content-0 and content-1 logs (should show services starting):"
echo "   docker logs vespa-content-0 2>&1 | tail -20"
echo "   docker logs vespa-content-1 2>&1 | tail -20"
echo ""
echo "3. Check content-2 logs (should show retrying/waiting for config):"
echo "   docker logs vespa-content-2 2>&1 | tail -20"
echo ""
echo "4. Test document API:"
echo "   curl http://localhost:8081/document/v1/airweave/chunk/docid/test1"
echo ""
