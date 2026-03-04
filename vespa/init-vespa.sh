#!/bin/sh
# Vespa application deployment script for Docker init container
# This script waits for Vespa to be ready and deploys the application package
set -e

# Install required packages (curl and zip)
apk add --no-cache curl zip > /dev/null 2>&1 || true

CONFIG_SERVER="${VESPA_CONFIG_SERVER:-http://vespa:19071}"
APP_DIR="/app"
BUILD_DIR="/tmp/vespa-build"
MAX_RETRIES=60
RETRY_INTERVAL=5

# Get embedding dimensions from environment (default: 1536 for OpenAI)
EMBEDDING_DIM="${EMBEDDING_DIMENSIONS:-1536}"

echo "=== Vespa Init Container ==="
echo "Config server: ${CONFIG_SERVER}"
echo "Application directory: ${APP_DIR}"
echo "Embedding dimensions: ${EMBEDDING_DIM}"

# Wait for config server to be ready
echo ""
echo "Waiting for Vespa config server to be ready..."
retries=0
until curl -sf "${CONFIG_SERVER}/state/v1/health" | grep -q '"up"'; do
    retries=$((retries + 1))
    if [ $retries -ge $MAX_RETRIES ]; then
        echo "ERROR: Config server not ready after $((MAX_RETRIES * RETRY_INTERVAL)) seconds"
        exit 1
    fi
    echo "  Config server not ready, waiting... (attempt ${retries}/${MAX_RETRIES})"
    sleep $RETRY_INTERVAL
done
echo "Config server is ready!"

# Check if application is already deployed
echo ""
echo "Checking if application is already deployed..."
status_code=$(curl -sf -o /dev/null -w "%{http_code}" "${CONFIG_SERVER}/application/v2/tenant/default/application/default" || echo "000")
if [ "$status_code" = "200" ]; then
    echo "Application already deployed, checking if update is needed..."
fi

# Template schema files with embedding dimensions
echo ""
echo "Templating schema files with EMBEDDING_DIM=${EMBEDDING_DIM}..."
rm -rf "${BUILD_DIR}"
cp -r "${APP_DIR}" "${BUILD_DIR}"

# Replace {{EMBEDDING_DIM}} placeholder in all schema files
for schema_file in "${BUILD_DIR}"/schemas/*.sd; do
    if [ -f "$schema_file" ]; then
        sed -i "s/{{EMBEDDING_DIM}}/${EMBEDDING_DIM}/g" "$schema_file"
    fi
done

# Create application package zip
echo ""
echo "Creating application package from ${BUILD_DIR}..."
cd "${BUILD_DIR}"
rm -f /tmp/app.zip
zip -rq /tmp/app.zip . -x ".*" -x "__MACOSX/*"
echo "Application package created: $(ls -lh /tmp/app.zip | awk '{print $5}')"

# Deploy application package
echo ""
echo "Deploying application package..."
deploy_response=$(curl -s -w "\n%{http_code}" --header "Content-Type:application/zip" \
    --data-binary @/tmp/app.zip \
    "${CONFIG_SERVER}/application/v2/tenant/default/prepareandactivate" 2>&1)
http_code=$(echo "${deploy_response}" | tail -1)
body=$(echo "${deploy_response}" | sed '$d')

if [ "$http_code" != "200" ]; then
    echo "ERROR: Deployment failed with HTTP ${http_code}"
    echo "Response: ${body}"
    exit 1
fi
echo "Deployment response:"
echo "${body}" | head -20

# Wait for application to converge (all services started)
echo ""
echo "Waiting for application to converge..."
retries=0
while [ $retries -lt $MAX_RETRIES ]; do
    converge_status=$(curl -sf "${CONFIG_SERVER}/application/v2/tenant/default/application/default/environment/prod/region/default/instance/default/serviceconverge" 2>/dev/null || echo '{"converged":false}')

    if echo "${converge_status}" | grep -q '"converged":true'; then
        echo "Application converged successfully!"
        break
    fi

    retries=$((retries + 1))
    if [ $retries -ge $MAX_RETRIES ]; then
        echo "WARNING: Application did not converge within timeout, but deployment was accepted"
        echo "Last status: ${converge_status}"
        break
    fi

    echo "  Waiting for convergence... (attempt ${retries}/${MAX_RETRIES})"
    sleep $RETRY_INTERVAL
done

# Verify document API is accessible and ready for documents
echo ""
echo "Verifying document API is accessible and ready..."
retries=0
MAX_DOC_API_RETRIES=60
DOC_API_READY=false

while [ $retries -lt $MAX_DOC_API_RETRIES ]; do
    # Try to query the document API endpoint to ensure it's actually ready
    # Using timeout and checking if curl succeeds at all (any HTTP response = API is up)
    if timeout 5 curl -s -o /dev/null -w "%{http_code}" "http://vespa:8081/document/v1/" > /tmp/vespa_status 2>&1; then
        doc_check=$(cat /tmp/vespa_status 2>/dev/null || echo "000")
        # Any HTTP response code (400, 404, 200, etc.) means API is responding
        # Only "000" means connection failed
        if [ "$doc_check" != "000" ] && [ -n "$doc_check" ]; then
            echo "✅ Document API is ready! (HTTP status: $doc_check)"
            DOC_API_READY=true
            rm -f /tmp/vespa_status
            break
        fi
    fi

    retries=$((retries + 1))
    if [ $retries -ge $MAX_DOC_API_RETRIES ]; then
        echo "❌ Document API not responding after ${MAX_DOC_API_RETRIES} attempts ($((MAX_DOC_API_RETRIES * 2))s)"
        rm -f /tmp/vespa_status
        break
    fi

    echo "  ⏳ Document API not ready, waiting... (attempt ${retries}/${MAX_DOC_API_RETRIES})"
    sleep 2
done

if [ "$DOC_API_READY" = "true" ]; then
    echo "✅ Document API verified and ready for requests!"
else
    echo "❌ Document API verification failed - Vespa not ready"
    exit 1
fi

echo ""
echo "=== Vespa initialization complete ==="
