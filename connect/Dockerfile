FROM node:22-slim AS builder
WORKDIR /app/connect

# Copy connect app files
COPY connect/package.json connect/package-lock.json ./
RUN npm ci --ignore-scripts

# Copy connect source code
COPY connect/ .

# Copy frontend icons to expected relative path (vite.config.ts uses ../frontend/...)
COPY frontend/src/components/icons/apps/ /app/frontend/src/components/icons/apps/

# Build the application
# This produces .output/ directory with server and public assets
RUN NODE_OPTIONS="--max-old-space-size=4096" npm run build

# Runtime stage
FROM node:22-alpine
WORKDIR /app

# Install wget for healthcheck
RUN apk add --no-cache wget

# Copy built app from builder stage
COPY --from=builder /app/connect/.output /app/.output
COPY connect/docker-entrypoint.sh /usr/local/bin/

# Make entrypoint executable
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Default port for Connect widget
ENV PORT=8082

# Expose the port
EXPOSE 8082

# Use entrypoint script for runtime configuration
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
