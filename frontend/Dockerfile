FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy application code
COPY . .

# Ensure auth0-provider.tsx exists (won't overwrite if it exists)
RUN mkdir -p /app/src/lib && \
    if [ ! -f /app/src/lib/auth0-provider.tsx ]; then \
    echo "Creating fallback auth0-provider.tsx"; \
    echo "import { ReactNode } from 'react';" > /app/src/lib/auth0-provider.tsx; \
    echo "export const Auth0ProviderWithNavigation = ({ children }: { children: ReactNode }) => <>{children}</>;" >> /app/src/lib/auth0-provider.tsx; \
    fi

# Build the application in production mode
RUN npm run build

# Runtime stage
FROM node:20-alpine

WORKDIR /app

# Install serve for hosting the built app
RUN npm install -g serve

# Copy built app from builder stage
COPY --from=builder /app/dist /app/dist
COPY docker-entrypoint.sh /usr/local/bin/

# Make entrypoint executable
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Use entrypoint script for runtime configuration
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
