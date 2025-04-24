#!/bin/sh
set -e

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

# Run the command
exec serve -s /app/dist -l 8080 --no-clipboard --no-port-switching
