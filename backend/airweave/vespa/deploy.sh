#!/bin/bash
set -euo pipefail

# Deploy Vespa application package to config server
# Usage: ./deploy.sh

CONFIG_SERVER="http://localhost:19071"
APP_DIR="$(dirname "$0")/app"

echo "Waiting for config server to be ready..."
until curl -s "${CONFIG_SERVER}/state/v1/health" | grep -q '"up"'; do
    echo "  Config server not ready, waiting..."
    sleep 5
done
echo "Config server is ready!"

echo ""
echo "Creating application package zip..."
cd "${APP_DIR}"
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

