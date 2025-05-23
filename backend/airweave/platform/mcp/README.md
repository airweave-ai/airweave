# Airweave MCP (Model Context Protocol) Integration

This module provides Model Context Protocol (MCP) integration for Airweave, allowing AI agents to interact with Airweave's functionality through a standardized protocol.

## What is MCP?

The Model Context Protocol (MCP) is a standardized way for AI assistants to connect to external tools and data sources. It's often described as "the USB-C port for AI" - providing a uniform way to connect LLMs to resources they can use.

MCP enables AI agents to:
- **Access data** through Resources (like GET endpoints)
- **Execute operations** through Tools (like POST endpoints)
- **Use templates** for parameterized data access
- **Follow interaction patterns** through defined prompts

## How Airweave MCP Works

The Airweave MCP integration automatically converts your existing FastAPI routes into MCP components:

| FastAPI Route Type | Example | MCP Component | Purpose |
|-------------------|---------|---------------|---------|
| GET without path params | `GET /collections` | **Resource** | Fetch data (e.g., list collections) |
| GET with path params | `GET /collections/{id}` | **Resource Template** | Parameterized data access |
| POST, PUT, DELETE | `POST /collections` | **Tool** | Operations that modify data |

### Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AI Agent      │    │   MCP Server    │    │  FastAPI App    │
│   (Claude, etc) │◄──►│   (FastMCP)     │◄──►│   (Airweave)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │                       │                       │
        ▼                       ▼                       ▼
   MCP Client              HTTP/ASGI               Existing APIs
  (SSE/HTTP)               Transport              (No changes!)
```

## Configuration

### Environment Variables

Add this to your `.env` file to enable MCP:

```bash
# Enable MCP functionality
MCP_ENABLED=true
```

### Dependencies

The MCP functionality requires the `fastmcp` package:

```bash
poetry add fastmcp
```

## Usage

### 1. Basic Setup

Once enabled, the MCP server is automatically mounted at `/mcp-server/mcp` alongside your existing API.

Your existing FastAPI application continues to work exactly as before - MCP is additive.

### 2. Check MCP Status

Visit the MCP info endpoints to verify everything is working:

```bash
# Check MCP status
curl http://localhost:8001/api/v1/mcp

# See what capabilities are available
curl http://localhost:8001/api/v1/mcp/capabilities

# View route mappings
curl http://localhost:8001/api/v1/mcp/routes
```

### 3. Connect an AI Agent

Configure your AI client to connect to the MCP server:

```json
{
  "mcpServers": {
    "airweave": {
      "command": "mcp-proxy",
      "args": ["http://localhost:8001/mcp-server/mcp"],
      "env": {
        "AIRWEAVE_API_TOKEN": "your-api-token-here"
      }
    }
  }
}
```

### 4. AI Agent Usage

Once connected, AI agents can:

```
# List all collections (Resource)
Agent: "Show me all collections in Airweave"

# Get specific collection (Resource Template)
Agent: "Get details for collection with ID abc123"

# Create new collection (Tool)
Agent: "Create a new collection called 'Customer Data' with PostgreSQL source"

# Start sync job (Tool)
Agent: "Start a sync for the Customer Data collection"

# Search across data (Tool)
Agent: "Search for 'customer complaints' across all collections"
```

## Available MCP Components

### Resources (Data Access)
- **Collections**: List and view data collections
- **Sources**: Available data source types
- **Destinations**: Configured vector/graph destinations
- **Sync Status**: Current synchronization status
- **Health**: System health information

### Tools (Operations)
- **Create Collections**: Set up new data collections
- **Configure Sources**: Connect new data sources
- **Start Syncs**: Trigger data synchronization
- **Manage API Keys**: Handle authentication
- **Search Data**: Query across synchronized data

### Resource Templates (Parameterized Access)
- **Collection by ID**: Access specific collections
- **Source Connection by ID**: Get connection details
- **Sync Job Status**: Check specific sync progress
- **Entity Details**: Access entity information

## ASGI Integration Details

The MCP server is integrated into Airweave's ASGI stack using FastMCP's ASGI integration:

```python
# In main.py
app = FastAPI(...)  # Your existing app

# MCP is mounted as a sub-application
if settings.MCP_ENABLED:
    mcp_app = get_mcp_app(app)
    app.mount("/mcp-server", mcp_app)
```

This approach ensures:
- ✅ **No interference** with existing APIs
- ✅ **Same ASGI stack** - shares middleware, auth, etc.
- ✅ **Graceful degradation** - app works fine if MCP is disabled
- ✅ **Production ready** - proper error handling and logging

## Security Considerations

### Authentication
- MCP endpoints inherit your existing FastAPI authentication
- API tokens or OAuth2 credentials are required
- All existing authorization rules apply

### Network Security
- MCP uses HTTP/ASGI transport (no additional ports)
- Can be secured with same TLS/SSL as main API
- Integrates with existing reverse proxy configuration

### Access Control
- MCP exposes same data/operations as regular API
- No additional permissions - uses existing RBAC
- Rate limiting and other protections apply

## Troubleshooting

### Common Issues

1. **MCP not available**
   ```
   MCP is enabled but FastMCP is not available - install fastmcp package
   ```
   **Solution**: Run `poetry add fastmcp`

2. **Import errors**
   ```
   Failed to mount MCP server: ImportError
   ```
   **Solution**: Check that all dependencies are installed

3. **Connection issues**
   ```
   Error inspecting MCP capabilities
   ```
   **Solution**: Verify the FastAPI app is properly initialized

### Debug Mode

For debugging, check the logs:

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Check MCP-specific logs
grep "MCP" logs/app.log
```

### Health Checks

Use the health endpoint to verify MCP is working:

```bash
curl http://localhost:8001/api/v1/mcp/capabilities
```

## Development

### Testing MCP Integration

```bash
# Test with a simple client
pip install mcp-client

# Connect and test
python -c "
import asyncio
from mcp import Client

async def test():
    client = Client('http://localhost:8001/mcp-server/mcp')
    tools = await client.list_tools()
    print(f'Available tools: {tools}')

asyncio.run(test())
"
```

### Adding Custom MCP Components

While FastMCP automatically converts routes, you can add custom MCP-specific functionality:

```python
# In your MCP server setup
@mcp_server.tool()
def custom_airweave_operation(param: str) -> str:
    """Custom operation specific to MCP clients."""
    return f"Custom operation with {param}"

@mcp_server.resource("custom-resource")
def custom_resource() -> str:
    """Custom resource for MCP clients."""
    return "Custom resource data"
```

## Performance Considerations

### Timeout Configuration
- Default timeout: 30 seconds for all API requests
- Configurable in `server.py`
- Applies to all MCP tool/resource calls

### Caching
- MCP leverages existing FastAPI caching
- No additional caching layer needed
- Resource responses follow same cache policies

### Monitoring
- MCP requests appear in standard API logs
- Use existing monitoring/metrics
- Monitor `/mcp-server/mcp` endpoint specifically

## Future Enhancements

Potential improvements for the MCP integration:

1. **Custom Authentication**: MCP-specific API keys
2. **Enhanced Streaming**: Real-time sync progress via SSE
3. **Agent Prompts**: Pre-defined interaction patterns
4. **Webhook Integration**: Proactive agent notifications
5. **Multi-tenant Support**: Organization-specific MCP endpoints

## References

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [FastMCP Documentation](https://gofastmcp.com/)
- [Anthropic MCP Guide](https://docs.anthropic.com/en/docs/build-with-claude/computer-use)
- [Claude Desktop MCP Configuration](https://docs.anthropic.com/en/docs/build-with-claude/computer-use#mcp-servers)
