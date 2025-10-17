# Airweave MCP Search Server

An MCP (Model Context Protocol) server that provides comprehensive search capabilities for Airweave collections. This server allows AI assistants to search through your Airweave data using natural language queries with full parameter control.

## Features

- 🔍 **Enhanced Search Tool**: Query Airweave collections with natural language and full parameter control
- 🤖 **AI Completion**: Get AI-processed responses from search results
- 📊 **Pagination Control**: Limit results and control pagination with offset
- ⏰ **Recency Bias**: Prioritize recent results with configurable recency weighting
- ⚙️ **Configuration Tool**: View current server configuration
- 🔐 **Secure**: Uses API key authentication
- 🌐 **Flexible**: Configurable base URL for different environments
- 🧪 **Comprehensive Testing**: Full test suite with LLM testing strategy
- 🏗️ **Simple Architecture**: Clean, maintainable code structure without over-engineering

## Deployment Modes

This MCP server supports two deployment modes:

### 1. Local Mode (Desktop AI Clients)

For **Claude Desktop, Cursor, and other desktop AI assistants**:
- Uses stdio transport (standard input/output)
- Runs as a subprocess on the user's machine
- Installed via npm package

### 2. Hosted Mode (Cloud AI Platforms)

For **OpenAI AgentBuilder and cloud-based AI platforms**:
- Uses HTTP/SSE transport (Server-Sent Events)
- Deployed to Azure Kubernetes Service
- Accessible via `https://mcp.airweave.ai`

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed hosting instructions.

## Quick Start (Local Mode)

### Installation from npm

The easiest way to use this server locally is via npx:

```bash
npx airweave-mcp-search
```

### Installation from Source

```bash
cd mcp
npm install
npm run build
npm run start
```

## Configuration

The server requires environment variables to connect to your Airweave instance:

### Required Environment Variables

- `AIRWEAVE_API_KEY`: Your Airweave API key (get this from your Airweave dashboard)
- `AIRWEAVE_COLLECTION`: The readable ID of the collection to search

### Optional Environment Variables

- `AIRWEAVE_BASE_URL`: Base URL for the Airweave API (default: `https://api.airweave.ai`)

## Usage with Cursor/Claude Desktop

### 1. Configure in Claude Desktop

Add the following to your Claude Desktop configuration file (`~/.cursor/mcp.json` or similar):

```json
{
  "mcpServers": {
    "airweave-search": {
      "command": "npx",
      "args": ["airweave-mcp-search"],
      "env": {
        "AIRWEAVE_API_KEY": "your-api-key-here",
        "AIRWEAVE_COLLECTION": "your-collection-id",
        "AIRWEAVE_BASE_URL": "https://api.airweave.ai"
      }
    }
  }
}
```

### 2. Local Development Configuration

For local development with a self-hosted Airweave instance:

```json
{
  "mcpServers": {
    "airweave-search": {
      "command": "node",
      "args": ["/absolute/path/to/airweave/mcp/build/index.js"],
      "env": {
        "AIRWEAVE_API_KEY": "your-api-key-here",
        "AIRWEAVE_COLLECTION": "your-collection-id",
        "AIRWEAVE_BASE_URL": "http://localhost:8001"
      }
    }
  }
}
```

### 3. Using the Tools

Once configured, you can use natural language to search:

- "Search for customer feedback about pricing"
- "Find documents related to API documentation"
- "Look up information about data privacy policies"

## Available Tools

### `search-{collection}`

Searches within the configured Airweave collection with full parameter control.

**Parameters:**

**Core Parameters:**
- `query` (required): The search query text to find relevant documents and data
- `response_type` (optional, default: "raw"): Format of the response: 'raw' returns search results, 'completion' returns AI-generated answers
- `limit` (optional, default: 100): Maximum number of results to return (1-1000)
- `offset` (optional, default: 0): Number of results to skip for pagination (≥0)
- `recency_bias` (optional): How much to weigh recency vs similarity (0..1). 0 = no recency effect; 1 = rank by recency only

**Advanced Parameters:**
- `score_threshold` (optional): Minimum similarity score threshold (0..1). Only return results above this score
- `search_method` (optional): Search method: 'hybrid' (default, combines neural + keyword), 'neural' (semantic only), 'keyword' (text matching only)
- `expansion_strategy` (optional): Query expansion strategy: 'auto' (default, generates query variations), 'llm' (AI-powered expansion), 'no_expansion' (use exact query)
- `enable_reranking` (optional): Enable LLM-based reranking to improve result relevance (default: true)
- `enable_query_interpretation` (optional): Enable automatic filter extraction from natural language query (default: true)

**Examples:**
```typescript
// Basic search
search({ query: "customer feedback about pricing" })

// Search with AI completion
search({
  query: "billing issues",
  response_type: "completion"
})

// Paginated search
search({
  query: "API documentation",
  limit: 10,
  offset: 20
})

// Recent results with recency bias
search({
  query: "customer complaints",
  recency_bias: 0.8
})

// Advanced search with high-quality results
search({
  query: "customer complaints",
  score_threshold: 0.8,
  search_method: "neural",
  enable_reranking: true
})

// Fast keyword search without expansion
search({
  query: "API documentation",
  search_method: "keyword",
  expansion_strategy: "no_expansion",
  enable_reranking: false
})

// Full parameter search
search({
  query: "support tickets",
  response_type: "completion",
  limit: 5,
  offset: 0,
  recency_bias: 0.7,
  score_threshold: 0.6,
  search_method: "hybrid",
  expansion_strategy: "llm",
  enable_reranking: true,
  enable_query_interpretation: true
})
```

### `get-config`

Shows the current server configuration and status.

**Parameters:** None

**Example:**
```
get-config()
```

## API Integration

This server interfaces with the Airweave Collections API:

- **Endpoint**: `GET /collections/{collection_id}/search`
- **Authentication**: `x-api-key` header
- **Query Parameters**:
  - `query`: Search query string
  - `response_type`: `RAW` or `COMPLETION`

## Testing

This MCP server includes comprehensive testing to ensure reliability and proper LLM interaction.

### Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run LLM-specific tests
npm run test:llm
```

### Test Categories

1. **Unit Tests**: Parameter validation and schema testing
2. **Integration Tests**: API calls and error handling
3. **LLM Tests**: How AI assistants interact with the enhanced parameters

### LLM Testing Strategy

The server includes a comprehensive LLM testing framework to evaluate how different AI assistants use the enhanced parameters:

- **Basic Tests**: Simple parameter usage
- **Advanced Tests**: Complex parameter combinations
- **Error Tests**: Invalid parameter handling
- **Edge Tests**: Boundary conditions and special cases

See `tests/llm-testing-strategy.md` for detailed testing methodology.

## Development

### Building from Source

1. Clone the repository:
```bash
git clone <repository-url>
cd airweave/mcp
```

2. Install dependencies:
```bash
npm install
```

3. Build the project:
```bash
npm run build
```

4. Run locally (stdio mode):
```bash
AIRWEAVE_API_KEY=your-key AIRWEAVE_COLLECTION=your-collection npm run start
```

5. Run locally (HTTP mode):
```bash
AIRWEAVE_API_KEY=your-key AIRWEAVE_COLLECTION=your-collection npm run start:http
```

### Development Workflow

```bash
# Build and run (stdio mode for desktop clients)
npm run dev

# Build and run (HTTP mode for testing cloud deployment)
npm run dev:http

# Build only
npm run build

# Run stdio version
npm run start

# Run HTTP version
npm run start:http

# Run tests
npm test
```

### Testing HTTP Mode Locally

```bash
# Start HTTP server
AIRWEAVE_API_KEY=your-key AIRWEAVE_COLLECTION=your-collection npm run start:http

# In another terminal, test health endpoint
curl http://localhost:8080/health

# Test SSE endpoint
curl http://localhost:8080/sse
```

## Error Handling

The server provides detailed error messages for common issues:

- **Missing API Key**: Clear message when `AIRWEAVE_API_KEY` is not set
- **Missing Collection**: Clear message when `AIRWEAVE_COLLECTION` is not set
- **API Errors**: Detailed error messages from the Airweave API
- **Network Issues**: Connection and timeout error handling

## Security

- API keys are never logged or exposed in responses
- All requests use HTTPS (when using the default base URL)
- Environment variables are validated at startup

## Troubleshooting

### Common Issues

1. **"Error: AIRWEAVE_API_KEY environment variable is required"**
   - Make sure you've set the `AIRWEAVE_API_KEY` environment variable
   - Check that your API key is valid and has access to the collection

2. **"Error: AIRWEAVE_COLLECTION environment variable is required"**
   - Set the `AIRWEAVE_COLLECTION` environment variable to your collection's readable ID
   - Verify the collection ID exists in your Airweave instance

3. **"Airweave API error (404)"**
   - Check that the collection ID is correct
   - Verify the collection exists and you have access to it

4. **"Airweave API error (401)"**
   - Check that your API key is valid
   - Ensure the API key has the necessary permissions

### Debug Mode

For debugging, you can check the stderr output where the server logs its startup information:

```bash
# The server logs to stderr (won't interfere with MCP protocol)
# Look for messages like:
# "Airweave MCP Search Server started"
# "Collection: your-collection-id"
# "Base URL: https://api.airweave.ai"
```

## Deployment to Production

For hosting the MCP server for cloud-based AI platforms:

1. **See [DEPLOYMENT.md](./DEPLOYMENT.md)** for comprehensive deployment guide
2. **Docker**: Uses provided Dockerfile for containerization
3. **Kubernetes**: Helm charts available in `/infra-core/helm/airweave/`
4. **Hosted URLs**:
   - Development: `https://mcp.dev-airweave.com`
   - Production: `https://mcp.airweave.ai`

Quick deployment:
```bash
# Build Docker image
docker build -t airweavecoreacr.azurecr.io/mcp:v1.0.0 .

# Push to Azure Container Registry
az acr login --name airweavecoreacr
docker push airweavecoreacr.azurecr.io/mcp:v1.0.0

# Deploy with Helm
cd /infra-core
./helm-upgrade.sh prd v1.0.0 airweave true
```

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- Check the [Airweave documentation](https://docs.airweave.ai)
- See [DEPLOYMENT.md](./DEPLOYMENT.md) for deployment issues
- Open an issue on GitHub
- Contact your Airweave administrator for API key and access issues
