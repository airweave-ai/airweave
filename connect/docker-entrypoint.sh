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

# Runtime config is served dynamically by server/routes/config.js.ts
# which reads process.env directly. No file generation needed.

# Start the Nitro server
# Nitro reads PORT from environment (default 3000, we set to 8082)
exec node /app/.output/server/index.mjs
