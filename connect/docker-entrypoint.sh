#!/bin/sh
set -e

# Input validation for environment variables
validate_url() {
  local value="$1"
  local name="$2"
  # Allow full URLs: http://... or https://...
  if ! echo "$value" | grep -qE '^https?://[a-zA-Z0-9][a-zA-Z0-9.-]*(:[0-9]+)?(/[a-zA-Z0-9/_-]*)?$'; then
    echo "ERROR: Invalid $name format: $value"
    echo "$name must be a full URL (http://... or https://...)"
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
