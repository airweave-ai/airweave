# Airweave MCP Search Server

[![npm version](https://img.shields.io/npm/v/airweave-mcp-search.svg)](https://www.npmjs.com/package/airweave-mcp-search)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js >= 20](https://img.shields.io/badge/node-%3E%3D20-brightgreen.svg)](https://nodejs.org/)
[![MCP Protocol](https://img.shields.io/badge/MCP-2025--03--26-blue.svg)](https://modelcontextprotocol.io/)

> **Official MCP server for Airweave** - Make your data searchable for AI assistants with semantic search, natural language queries, and advanced filtering.

An MCP (Model Context Protocol) server that provides comprehensive search capabilities for Airweave collections. This server allows AI assistants (Claude, Cursor, OpenAI agents, etc.) to search through your Airweave data using natural language queries with full parameter control.

**Compatibility:**
- MCP Protocol: 2025-03-26 (Streamable HTTP) + legacy stdio
- Node.js: 20.0.0 or higher
- Works with: Claude Desktop, Cursor, OpenAI Agent Builder, and any MCP-compatible client
- Airweave API: v1.0+

---

## Table of Contents

- [Quick Example](#quick-example)
- [Why Use This MCP Server?](#why-use-this-mcp-server)
- [Features](#features)
- [Deployment Modes](#deployment-modes)
- [Quick Start (Local Mode)](#quick-start-local-mode)
- [Configuration](#configuration)
- [Authentication](#authentication)
- [Usage with Cursor/Claude Desktop](#usage-with-cursorClaude-desktop)
- [Available Tools](#available-tools)
- [Testing](#testing)
- [Development](#development)
- [Deployment to Production](#deployment-to-production)
- [Troubleshooting](#troubleshooting)
- [Architecture Overview](#architecture-overview)
- [Support](#support)

---

**What makes this special:**
- **True Multi-tenancy**: Hosted mode supports thousands of users with per-session isolation
- **Production-Ready**: Redis-backed sessions, rate limiting, OAuth2 support, comprehensive logging
- **Advanced Search**: Hybrid search, query expansion, reranking, recency bias, and more
- **Developer-Friendly**: Works with both desktop clients (stdio) and cloud platforms (HTTP)
- **Fully Tested**: Comprehensive test suite including HTTP transport and session management

## Quick Example

```bash
# Install and configure
npx airweave-mcp-search

# Use in Claude Desktop - add to config:
{
  "mcpServers": {
    "airweave": {
      "command": "npx",
      "args": ["airweave-mcp-search"],
      "env": {
        "AIRWEAVE_API_KEY": "your-key",
        "AIRWEAVE_COLLECTION": "your-collection-id"
      }
    }
  }
}

# Then in Claude:
# "Search for customer feedback about pricing"
# "Find the most recent documents about API changes"
# "Show me support tickets from the last week"
```

## Why Use This MCP Server?

**For AI Assistant Users:**
- Search your company's knowledge base directly from Claude Desktop or Cursor
- Get AI-generated summaries of search results automatically
- Use natural language - no need to learn complex query syntax
- Works with any data source Airweave supports (APIs, databases, file systems, etc.)

**For Developers:**
- Production-ready hosted mode for building AI applications
- OAuth2 integration for secure user authentication
- Horizontal scaling with Redis-backed sessions
- Comprehensive API with 10+ configurable parameters

**For Enterprises:**
- Multi-tenant architecture - one deployment serves all users
- Built-in rate limiting and security features
- Audit logging for compliance
- Works with existing Airweave infrastructure

## Features

- **Enhanced Search Tool**: Query Airweave collections with natural language and full parameter control
- **AI Completion**: Get AI-processed responses from search results
- **Pagination Control**: Limit results and control pagination with offset
- **Recency Bias**: Prioritize recent results with configurable recency weighting
- **Configuration Tool**: View current server configuration
- **Secure**: Multiple authentication methods (API keys, OAuth2)
- **Multi-tenant**: True multi-tenancy with per-session isolation in hosted mode
- **Scalable**: Redis-backed session management for horizontal scaling
- **Rate Limited**: Built-in rate limiting to prevent abuse
- **Flexible**: Configurable base URL for different environments
- **Comprehensive Testing**: Full test suite with LLM testing strategy
- **Simple Architecture**: Clean, maintainable code structure without over-engineering

## Deployment Modes

This MCP server supports two deployment modes with different use cases:

### 1. Local Mode (Desktop AI Clients)

For **Claude Desktop, Cursor, and other desktop AI assistants**:
- Uses stdio transport (standard input/output)
- Runs as a subprocess on the user's machine
- Installed via npm package

### 2. Hosted Mode (Cloud AI Platforms)

For **OpenAI AgentBuilder and cloud-based AI platforms**:
- Uses Streamable HTTP transport (MCP 2025-03-26)
- Deployed to Azure Kubernetes Service
- Accessible via `https://mcp.airweave.ai`
- **Multi-tenant**: Each user provides their own API key per request
- **Session Management**: Redis-backed sessions for horizontal scaling
- **Rate Limiting**: 100 sessions per hour per API key
- **Security**: API key hashing, session binding (IP/User-Agent), audit logging

**Architecture Highlights:**
- **Per-Session Isolation**: Separate `McpServer` instances per session/API key
- **Distributed Sessions**: Redis stores session metadata, local cache for performance
- **Stateless Design**: Any pod can handle any request after session retrieval
- **Automatic Cleanup**: 30-minute session TTL with automatic expiration

**Configuration for OpenAI Agent Builder:**
```
MCP Server URL: https://mcp.airweave.ai/mcp

Custom Headers:
  Header 1:
    name: X-API-Key
    value: <your-airweave-api-key>
  
  Header 2:
    name: X-Collection-Readable-ID
    value: <your-collection-readable-id>
```

**Alternative: OAuth2 Authentication (Recommended for Production)**
```
MCP Server URL: https://mcp.airweave.ai/mcp

Custom Headers:
  Header 1:
    name: Authorization
    value: Bearer <oauth-access-token>
```

> OAuth tokens are validated and cached for performance. Collection access is determined automatically from your account.

## Quick Start (Local Mode)

### Installation from npm

The easiest way to use this server locally is via npx:

```bash
# Run directly with npx (recommended)
npx airweave-mcp-search

# Or install globally
npm install -g airweave-mcp-search
airweave-mcp-search
```

### Installation from Source

```bash
cd mcp
npm install
npm run build
npm run start
```

### Development Installation Script

For developers building from source, use the provided install script:

```bash
# Clone the repository first
git clone https://github.com/airweave-ai/airweave.git
cd airweave/mcp

# Run the install script
./install.sh
```

This script will:
1. Check Node.js version (20+ required)
2. Install dependencies
3. Build the TypeScript project
4. Run tests
5. Provide next steps for configuration

> **Note**: For end-users, we recommend using `npx airweave-mcp-search` instead of building from source.

## Configuration

### Local Mode Configuration

The server requires environment variables to connect to your Airweave instance:

**Required Environment Variables:**
- `AIRWEAVE_API_KEY`: Your Airweave API key (get this from your Airweave dashboard)
- `AIRWEAVE_COLLECTION`: The readable ID of the collection to search

**Optional Environment Variables:**
- `AIRWEAVE_BASE_URL`: Base URL for the Airweave API (default: `https://api.airweave.ai`)

### Hosted Mode Configuration

For cloud-based AI platforms (OpenAI Agent Builder, etc.), configuration is provided via **custom headers** instead of environment variables:

**Required Headers:**
- `X-API-Key`: Your Airweave API key
- `X-Collection-Readable-ID`: The readable ID of the collection to search

**Optional Headers:**
- None (base URL is configured at deployment)

This approach enables **true multi-tenancy**: each user can search their own collections without requiring separate server deployments.

## Authentication

The MCP server supports multiple authentication methods:

### API Key Authentication (Local & Hosted Mode)

**Local Mode (Environment Variable):**
```bash
export AIRWEAVE_API_KEY="your-api-key-here"
```

**Hosted Mode (HTTP Headers):**
- `Authorization: Bearer <api-key>`
- `X-API-Key: <api-key>`
- Query parameters: `?apiKey=<key>` or `?api_key=<key>`

**Security Features:**
- API keys are hashed (SHA-256) before storage in Redis
- Keys are never logged or exposed in error messages
- Session binding prevents hijacking (IP + User-Agent)

### OAuth2 Authentication (Hosted Mode Only)

OAuth2 provides more secure authentication for production deployments:

**Authorization Flow:**
1. User authorizes via Airweave OAuth consent page
2. Application receives OAuth access token
3. Token is sent in `Authorization: Bearer <token>` header
4. MCP server validates token and caches result (1-hour TTL)

**Benefits:**
- Fine-grained access control
- Token revocation support
- Automatic collection discovery
- Better audit trail

**Example (OpenAI Agent Builder):**
```
MCP Server URL: https://mcp.airweave.ai/mcp

Custom Headers:
  Header 1:
    name: Authorization
    value: Bearer <oauth-access-token>
```

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

### Local Mode Issues

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

### Hosted Mode Issues

1. **"Rate limit exceeded"**
   - You've created more than 100 sessions in the past hour
   - Wait for the rate limit window to reset or contact support for increased limits

2. **"Session not found"**
   - Session expired after 30 minutes of inactivity
   - Create a new session by making a request without the `mcp-session-id` header

3. **"Invalid OAuth token"**
   - Token may be expired or revoked
   - Obtain a new OAuth access token through the authorization flow

4. **"Redis connection failed"**
   - Check Redis server is running and accessible
   - Verify `REDIS_URL` environment variable is correct
   - Check network connectivity between MCP server and Redis

5. **"Session binding mismatch"**
   - Your IP address or User-Agent changed during the session
   - This is a security feature - create a new session

### Debug Mode

For debugging, you can check the stderr output where the server logs its startup information:

```bash
# Local Mode - logs to stderr (won't interfere with MCP protocol)
# Look for messages like:
# "Airweave MCP Search Server started"
# "Collection: your-collection-id"
# "Base URL: https://api.airweave.ai"

# Hosted Mode - check container logs for structured JSON logs:
kubectl logs -n airweave deployment/mcp-server

# Example log entries:
# {"timestamp":"2026-02-02T10:00:00.000Z","service":"mcp-redis-session","operation":"session_created",...}
# {"timestamp":"2026-02-02T10:00:05.000Z","service":"mcp-redis-session","operation":"session_accessed",...}
```

### Performance Tips

1. **Session Reuse**: Include `mcp-session-id` header to reuse sessions and avoid rate limits
2. **Caching**: OAuth tokens are cached for 1 hour - no need to refresh frequently
3. **Pagination**: Use `limit` and `offset` for large result sets instead of fetching everything
4. **Search Method**: Use `keyword` search with `no_expansion` for fastest response times

### Testing Hosted Mode

You can test the hosted MCP server using curl:

```bash
# 1. Check server health
curl https://mcp.airweave.ai/health

# 2. Get server info
curl https://mcp.airweave.ai/

# 3. List available tools (API Key Auth)
curl -X POST https://mcp.airweave.ai/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -H "X-Collection-Readable-ID: your-collection-id" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }'

# 4. List available tools (OAuth2)
curl -X POST https://mcp.airweave.ai/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-oauth-token" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }'

# 5. Execute a search
curl -X POST https://mcp.airweave.ai/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -H "X-Collection-Readable-ID: your-collection-id" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "search-your-collection-id",
      "arguments": {
        "query": "test query",
        "limit": 5
      }
    },
    "id": 2
  }'

# 6. Session management - subsequent requests use same session
curl -X POST https://mcp.airweave.ai/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -H "X-Collection-Readable-ID: your-collection-id" \
  -H "mcp-session-id: your-session-id-from-previous-response" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "search-your-collection-id",
      "arguments": {
        "query": "another query"
      }
    },
    "id": 3
  }'
```

**Session Handling:**
- First request creates a new session with ID returned in response headers
- Include `mcp-session-id` header in subsequent requests for session continuity
- Sessions expire after 30 minutes of inactivity
- Rate limit: 100 session creations per hour per API key

## Deployment to Production

For hosting the MCP server for cloud-based AI platforms:

### Prerequisites
- **Docker**: For containerization
- **Kubernetes**: For orchestration
- **Redis**: For session management and caching
- **Azure Container Registry**: For image storage

### Deployment Steps

1. **Build Docker Image**
```bash
docker build -t airweavecoreacr.azurecr.io/mcp:v1.0.0 .
```

2. **Push to Azure Container Registry**
```bash
az acr login --name airweavecoreacr
docker push airweavecoreacr.azurecr.io/mcp:v1.0.0
```

3. **Deploy with Helm**
```bash
cd /infra-core
./helm-upgrade.sh prd v1.0.0 airweave true
```

### Environment Configuration

**Required Environment Variables:**
- `AIRWEAVE_COLLECTION`: Default collection ID (can be overridden per request)
- `AIRWEAVE_BASE_URL`: Airweave API endpoint
- `REDIS_URL`: Redis connection string (e.g., `redis://redis:6379`)
- `PORT`: HTTP server port (default: 8080)

**Optional:**
- `REDIS_PASSWORD`: Redis authentication password
- `LOG_LEVEL`: Logging verbosity (default: info)

### Hosted Endpoints
- **Development**: `https://mcp.dev-airweave.com`
- **Production**: `https://mcp.airweave.ai`

### Health Checks
- **Health**: `GET /health` - Returns server status
- **Info**: `GET /` - Returns server info and available endpoints

## Architecture Overview

### Local Mode (Stdio Transport)
```
Claude Desktop/Cursor → Stdio Transport → MCP Server → Airweave API
                     ↑
                Environment Variables (API Key, Collection)
```

### Hosted Mode (HTTP Transport)
```
Cloud AI Platform → HTTPS → Load Balancer → MCP HTTP Server (Pod 1, 2, 3...)
                                                    ↓
                                            Redis Session Store
                                                    ↓
                                            Airweave API
```

**Key Components:**
- **Session Manager**: Redis-backed distributed sessions with local caching
- **OAuth Validator**: Token validation with 1-hour caching
- **Rate Limiter**: Per-API-key rate limiting (100 sessions/hour)
- **Transport Layer**: Stdio (local) or Streamable HTTP (hosted)

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- **Documentation**: [Airweave Docs](https://docs.airweave.ai)
- **GitHub Issues**: [Report bugs or request features](https://github.com/airweave-ai/airweave/issues)
- **API Access**: Contact your Airweave administrator for API keys
- **Security Issues**: See [SECURITY.md](../SECURITY.md) for reporting vulnerabilities

## Contributing

Contributions are welcome! Please read our [Contributing Guide](../CONTRIBUTING.md) before submitting PRs.
