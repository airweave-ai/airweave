#!/bin/bash
# Run Asana integration test

echo "🚀 Running Asana integration test..."
echo ""
echo "Make sure you have configured one of the following:"
echo "  1. Direct auth: export ASANA_ACCESS_TOKEN=your_token"
echo "  2. Provider auth: export DM_AUTH_PROVIDER=composio DM_AUTH_PROVIDER_API_KEY=comp_xxx"
echo ""

# Optional: Set Airweave API URL if not using localhost:8000
# export AIRWEAVE_API_URL=http://localhost:8001

# Run the test
python test_asana_integration.py
