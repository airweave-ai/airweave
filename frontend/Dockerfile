FROM node:20-slim AS builder

WORKDIR /app

# Copy package files
COPY package.json ./

# First install dependencies without using the lockfile
# Skip postinstall scripts to avoid @swc/core segfault
RUN npm install --no-package-lock --ignore-scripts

# Copy application code
COPY . .

# Build the application in production mode
# Increase Node memory and use npx to run vite directly
RUN NODE_OPTIONS="--max-old-space-size=4096" npx vite build

# Runtime stage
FROM node:20-alpine

WORKDIR /app

# Install serve for hosting the built app
RUN npm install -g serve

# Copy built app from builder stage
COPY --from=builder /app/dist /app/dist
COPY docker-entrypoint.sh /usr/local/bin/
COPY serve.json /app/serve.json

# Make entrypoint executable
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Use entrypoint script for runtime configuration
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
