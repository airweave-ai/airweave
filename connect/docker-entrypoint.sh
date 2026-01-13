#!/bin/sh
set -e

# Input validation for environment variables
validate_url() {
  # Allow full URLs: http://... or https://...
  if ! echo "$1" | grep -qE '^https?://[a-zA-Z0-9][a-zA-Z0-9.-]*(:[0-9]+)?(/[a-zA-Z0-9/_-]*)?$'; then
    echo "ERROR: Invalid $2 format: $1"
    echo "$2 must be a full URL (http://... or https://...)"
    exit 1
  fi
}

# Validate API_URL if provided
if [ -n "$API_URL" ]; then
  validate_url "$API_URL" "API_URL"
fi

# Set default API_URL if not provided
API_URL="${API_URL:-http://localhost:8001}"

echo "Connect widget starting with API_URL=${API_URL}"

# Create runtime config for client-side JavaScript
# This is injected into the HTML and read by the env.ts module
cat > /app/.output/public/config.js << EOF
window.__CONNECT_ENV__ = {
  API_URL: "${API_URL}"
};
EOF

echo "Runtime config generated successfully"

# Start the Nitro server
# Nitro reads PORT from environment (default 3000, we set to 8082)
exec node /app/.output/server/index.mjs
