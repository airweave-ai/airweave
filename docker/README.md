# Docker Compose Configurations

This directory contains Docker Compose configurations for running Airweave in different environments.

## Files

- **`docker-compose.yml`**: Production-like deployment with pre-built images
- **`docker-compose.dev.yml`**: Local development with infrastructure services only
- **`docker-compose.test.yml`**: Testing environment with isolated ports

## Services

### Core Infrastructure
- **postgres**: PostgreSQL database (port 5432)
- **redis**: Redis cache and PubSub (port 6379)
- **qdrant**: Vector database (port 6333)
- **temporal**: Workflow orchestration (port 7233)
- **temporal-ui**: Temporal web UI (port 8088)

### Application Services
- **backend**: FastAPI backend (port 8001)
- **frontend**: React/TypeScript frontend (port 8080)
- **temporal-worker**: Python workers for async operations
- **mcp**: MCP server for AI assistant integrations (port 8090)

### Supporting Services
- **text2vec-transformers**: Local embeddings (port 9878)
- **minio**: S3-compatible storage (port 9000/9001)

## MCP Server

The MCP (Model Context Protocol) server provides search capabilities for AI assistants like OpenAI Agent Builder and Claude Desktop.

### Usage

#### Development (docker-compose.dev.yml)
```bash
docker-compose -f docker-compose.dev.yml up -d mcp
```

The MCP server will be available at `http://localhost:8090`

**Note**: In dev mode, the MCP service expects the backend to be running separately (e.g., via VS Code debugger).

#### Production (docker-compose.yml)
```bash
# Start with MCP profile enabled
docker-compose --profile mcp up -d

# Or enable it in your .env
echo "COMPOSE_PROFILES=mcp" >> ../.env
docker-compose up -d
```

The MCP server is optional by default (uses profile) and will:
- Wait for the backend to be healthy before starting
- Automatically discover collections via the backend API
- Register search tools dynamically per API key

#### Testing (docker-compose.test.yml)
```bash
docker-compose -f docker-compose.test.yml up -d
```

All services including MCP will start on alternate ports (9xxx range).

### MCP Endpoints

- **Health Check**: `http://localhost:8090/health`
- **Server Info**: `http://localhost:8090/`
- **MCP Protocol**: `http://localhost:8090/mcp` (POST)

### Authentication

The MCP server requires an Airweave API key:
- **Header**: `Authorization: Bearer <your-api-key>`
- **Header**: `X-API-Key: <your-api-key>`
- **Query**: `?apiKey=<your-api-key>`

### Configuration

Environment variables:
- `PORT`: Server port (default: 8080)
- `AIRWEAVE_BASE_URL`: Backend API URL (default: http://backend:8001 in containers)
- `NODE_ENV`: Environment mode (development/production/test)
- `MCP_PORT`: External port mapping (default: 8090)

## Port Mapping Summary

### Development (docker-compose.dev.yml)
- PostgreSQL: 5432
- Redis: 6379
- Qdrant: 6333
- Temporal: 7233, 8233
- Temporal UI: 8088
- Embeddings: 9878
- MinIO: 9000, 9001
- **MCP: 8090**

### Testing (docker-compose.test.yml)
- PostgreSQL: 9432
- Redis: 9379
- Qdrant: 9333
- Temporal: Not included
- Backend: 9001
- Embeddings: 9080
- **MCP: 9090**

### Production (docker-compose.yml)
Uses same ports as development, plus:
- Backend: 8001
- Frontend: 8080
- **MCP: 8090** (with --profile mcp)

## Profiles

The production docker-compose.yml supports profiles to control which services run:

- **`frontend`**: Enable the frontend service (not needed for API-only testing)
- **`local-embeddings`**: Use local embedding model instead of OpenAI
- **`mcp`**: Enable MCP server for AI assistant integrations

Example:
```bash
# Start everything with MCP and frontend
docker-compose --profile frontend --profile mcp up -d

# Or set in .env
COMPOSE_PROFILES=frontend,mcp
```

## Development Workflow

1. **Start infrastructure only**:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

2. **Run backend/frontend from VS Code** for debugging

3. **Optionally start MCP** if testing AI integrations:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d mcp
   ```

4. **Test MCP**:
   ```bash
   curl http://localhost:8090/health
   ```

## Troubleshooting

### MCP server can't connect to backend
- Ensure backend is healthy: `docker-compose ps backend`
- Check backend logs: `docker-compose logs backend`
- Verify network connectivity: `docker-compose exec mcp wget -O- http://backend:8001/health`

### MCP shows no collections
- Verify API key has access to collections
- Check backend collections endpoint: `curl http://localhost:8001/collections -H "X-API-Key: your-key"`
- Review MCP logs: `docker-compose logs mcp`

### Port conflicts
- Check if ports are in use: `lsof -i :8090`
- Override port in .env: `MCP_PORT=8091`

