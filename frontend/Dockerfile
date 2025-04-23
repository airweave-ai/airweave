FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies with npm ci for consistent builds
RUN npm install && npm ci

# Copy application code
COPY . .

# Fix for module resolution during build
ENV NODE_PATH=/app/src

# Build the application
RUN npm run build

# Use serve to serve the static content
RUN npm install -g serve

# Copy entrypoint script to standard location and make executable
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Use entrypoint script for runtime configuration
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
