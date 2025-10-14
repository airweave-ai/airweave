#!/bin/sh
set -e

# CASA-6: Input validation for environment variables
validate_url_path() {
  local path="$1"
  # Allow paths starting with / containing only safe characters
  if ! echo "$path" | grep -qE '^/[a-zA-Z0-9/_-]*$'; then
    echo "ERROR: Invalid URL path format: $path"
    echo "URL path must start with / and contain only alphanumeric, -, _, / characters"
    exit 1
  fi
}

validate_domain() {
  local domain="$1"
  # Basic domain validation (alphanumeric, dots, hyphens)
  if ! echo "$domain" | grep -qE '^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]$'; then
    echo "ERROR: Invalid domain format: $domain"
    exit 1
  fi
}

validate_client_id() {
  local client_id="$1"
  # Basic alphanumeric validation
  if ! echo "$client_id" | grep -qE '^[a-zA-Z0-9_-]+$'; then
    echo "ERROR: Invalid client ID format"
    exit 1
  fi
}

validate_audience() {
  local audience="$1"
  # URL or URN validation
  if ! echo "$audience" | grep -qE '^(https?://|urn:)[a-zA-Z0-9:/.@_-]+$'; then
    echo "ERROR: Invalid audience format"
    exit 1
  fi
}

# Validate API_URL if provided
if [ -n "$API_URL" ]; then
  validate_url_path "$API_URL"
fi

# Validate Auth0 variables if provided
if [ -n "$AUTH0_DOMAIN" ]; then
  validate_domain "$AUTH0_DOMAIN"
fi

if [ -n "$AUTH0_CLIENT_ID" ]; then
  validate_client_id "$AUTH0_CLIENT_ID"
fi

if [ -n "$AUTH0_AUDIENCE" ]; then
  validate_audience "$AUTH0_AUDIENCE"
fi

# Determine if auth should be enabled
# Priority: 1. ENABLE_AUTH env var 2. If AUTH0 vars present 3. Default off
if [ "${ENABLE_AUTH}" = "true" ]; then
  AUTH_ENABLED=true
elif [ -n "$AUTH0_DOMAIN" ] && [ -n "$AUTH0_CLIENT_ID" ] && [ -n "$AUTH0_AUDIENCE" ]; then
  AUTH_ENABLED=true
  echo "Auth enabled because Auth0 credentials are provided"
else
  AUTH_ENABLED=false
  echo "Auth disabled (no credentials or ENABLE_AUTH not set to true)"
fi

# Create config.js with runtime environment variables
echo "Generating runtime config with API_URL=${API_URL:-/api}"
cat > /app/dist/config.js << EOF
window.ENV = {
  API_URL: "${API_URL:-/api}",
  AUTH_ENABLED: ${AUTH_ENABLED},
  AUTH0_DOMAIN: "${AUTH0_DOMAIN:-}",
  AUTH0_CLIENT_ID: "${AUTH0_CLIENT_ID:-}",
  AUTH0_AUDIENCE: "${AUTH0_AUDIENCE:-}"
};
console.log("Runtime config loaded:", window.ENV);
EOF

# Make sure config.js is loaded before any other scripts
# First, backup the original index.html
cp /app/dist/index.html /app/dist/index.html.bak

# Insert config.js in the <head> section to ensure it loads first
sed -i 's|</head>|  <script src="/config.js"></script>\n  </head>|' /app/dist/index.html

echo "Runtime config injected successfully. API_URL set to: ${API_URL:-/api}"

# Copy serve.json to dist directory for security headers (CASA-6)
if [ -f /app/serve.json ]; then
  cp /app/serve.json /app/dist/serve.json
  echo "Security headers configuration loaded"
fi

# Run the command with serve.json configuration
exec serve -s /app/dist -l 8080 --no-clipboard --no-port-switching
