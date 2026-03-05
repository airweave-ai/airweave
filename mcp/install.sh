#!/bin/bash

set -e

echo "🚀 Setting up Airweave MCP Search Server..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 20+ first."
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 20 ]; then
    echo "❌ Node.js 20+ is required. Current version: $(node -v)"
    exit 1
fi

echo "✅ Node.js $(node -v) detected"

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Build the project
echo "🔨 Building the project..."
npm run build

# Run tests
echo "🧪 Running tests..."
npm test

echo "✅ Build completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Set up your environment variables:"
echo "   - AIRWEAVE_API_KEY: Your API key"
echo "   - AIRWEAVE_COLLECTION: Your collection ID"
echo "   - AIRWEAVE_BASE_URL: API base URL (optional)"
echo ""
echo "2. Test locally:"
echo "   AIRWEAVE_API_KEY=your-key AIRWEAVE_COLLECTION=your-collection npm start"
echo ""
echo "3. Configure in Cursor using cursor-config-example.json"
echo ""
echo "4. Optional - Publish to npm:"
echo "   npm publish"
