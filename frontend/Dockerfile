FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Build the application
RUN npm run build

# Use serve to serve the static content
RUN npm install -g serve

# Simple runtime configuration with direct shell command
CMD sh -c 'echo "window.ENV = { API_URL: \"${API_URL:-/api}\" };" > ./dist/config.js && serve -s dist -l 8080'
