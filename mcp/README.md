# Airweave MCP Search Server

An MCP (Model Context Protocol) server that provides search capabilities for Airweave collections. This server allows AI assistants to search through your Airweave data using natural language queries.

## Features

- 🔍 **Search Tool**: Query Airweave collections with natural language
- 🤖 **AI Completion**: Get AI-processed responses from search results
- ⚙️ **Configuration Tool**: View current server configuration
- 🔐 **Secure**: Uses API key authentication
- 🌐 **Flexible**: Configurable base URL for different environments

## Quick Start

### Installation from npm

The easiest way to use this server is via npx:

```bash
npx airweave-mcp-search
```

### Installation from GitHub

You can also install directly from the GitHub repository:

```bash
npm install -g https://github.com/your-org/airweave-mcp-search.git
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

### `search`

Searches within the configured Airweave collection.

**Parameters:**
- `query` (required): The search query to execute
- `response_type` (optional): Either `"RAW"` for search results or `"COMPLETION"` for AI-processed response

**Example:**
```
search("customer feedback about pricing", "RAW")
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

4. Run locally:
```bash
AIRWEAVE_API_KEY=your-key AIRWEAVE_COLLECTION=your-collection npm run start
```

### Development Workflow

```bash
# Build and run
npm run dev

# Build only
npm run build

# Run built version
npm run start
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

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- Check the [Airweave documentation](https://docs.airweave.ai)
- Open an issue on GitHub
- Contact your Airweave administrator for API key and access issues
