#!/usr/bin/env node

/**
 * Airweave MCP Server - HTTP/Streamable Transport
 * 
 * This is the production HTTP server for cloud-based AI platforms like OpenAI Agent Builder.
 * Uses the modern Streamable HTTP transport (MCP 2025-03-26) instead of deprecated SSE.
 * 
 * Endpoint: https://mcp.airweave.ai/mcp
 * Protocol: MCP 2025-03-26 (Streamable HTTP)
 * Authentication: Bearer token, X-API-Key, or query parameter
 */

import express from 'express';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { AirweaveClient } from './api/airweave-client.js';
import { createSearchTool } from './tools/search-tool.js';
import { createConfigTool } from './tools/config-tool.js';

const app = express();
app.use(express.json({ limit: '10mb' }));

// Create MCP server instance with tools
const createMcpServer = (apiKey: string) => {
    const collection = process.env.AIRWEAVE_COLLECTION || 'default';
    const baseUrl = process.env.AIRWEAVE_BASE_URL || 'https://api.airweave.ai';

    const config = {
        collection,
        baseUrl,
        apiKey // Use the provided API key from the request
    };

    const server = new McpServer({
        name: 'airweave-search',
        version: '2.1.0',
    }, {
        capabilities: {
            tools: {},
            logging: {}
        }
    });

    // Create dynamic tool name based on collection
    const toolName = `search-${collection}`;

    // Initialize Airweave client with the request's API key
    const airweaveClient = new AirweaveClient(config);

    // Create tools using shared tool creation functions
    const searchTool = createSearchTool(toolName, collection, airweaveClient);
    const configTool = createConfigTool(toolName, collection, baseUrl, apiKey);

    // Register tools
    server.tool(
        searchTool.name,
        searchTool.description,
        searchTool.schema,
        searchTool.handler
    );

    server.tool(
        configTool.name,
        configTool.description,
        configTool.schema,
        configTool.handler
    );

    return server;
};

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        transport: 'streamable-http',
        protocol: 'MCP 2025-03-26',
        collection: process.env.AIRWEAVE_COLLECTION || 'unknown',
        timestamp: new Date().toISOString()
    });
});

// Root endpoint with server info
app.get('/', (req, res) => {
    const collection = process.env.AIRWEAVE_COLLECTION || 'default';
    const baseUrl = process.env.AIRWEAVE_BASE_URL || 'https://api.airweave.ai';

    res.json({
        name: "Airweave MCP Search Server",
        version: "2.1.0",
        transport: "Streamable HTTP",
        protocol: "MCP 2025-03-26",
        collection: collection,
        endpoints: {
            health: "/health",
            mcp: "/mcp"
        },
        authentication: {
            required: true,
            methods: [
                "Authorization: Bearer <your-api-key> (recommended for OpenAI Agent Builder)",
                "X-API-Key: <your-api-key>",
                "Query parameter: ?apiKey=your-key",
                "Query parameter: ?api_key=your-key"
            ],
            openai_agent_builder: {
                url: "https://mcp.airweave.ai/mcp",
                headers: {
                    Authorization: "Bearer <your-airweave-api-key>"
                }
            }
        }
    });
});

// Session management: Map session IDs to { server, transport, apiKey }
const sessions = new Map<string, {
    server: McpServer,
    transport: StreamableHTTPServerTransport,
    apiKey: string
}>();

// Main MCP endpoint (Streamable HTTP)
app.post('/mcp', async (req, res) => {
    try {
        // Extract API key from request headers or query parameters
        const apiKey = req.headers['x-api-key'] ||
            req.headers['authorization']?.replace('Bearer ', '') ||
            req.query.apiKey ||
            req.query.api_key;

        if (!apiKey) {
            res.status(401).json({
                jsonrpc: '2.0',
                error: {
                    code: -32001,
                    message: 'Authentication required',
                    data: 'Please provide an API key via X-API-Key header, Authorization header, or apiKey query parameter'
                },
                id: req.body.id || null
            });
            return;
        }

        // Get or create session ID from MCP-Session-ID header
        const sessionId = req.headers['mcp-session-id'] as string || `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        // Check if we have an existing session
        let session = sessions.get(sessionId);

        if (!session) {
            console.log(`[${new Date().toISOString()}] Creating new session: ${sessionId}`);

            // Create a new server with the API key
            const server = createMcpServer(apiKey as string);

            // Create a new transport for this session
            const transport = new StreamableHTTPServerTransport({
                sessionIdGenerator: () => sessionId
            });

            // Set up session management callbacks
            (transport as any).onsessioninitialized = (sid: string) => {
                console.log(`[${new Date().toISOString()}] Session initialized: ${sid}`);
            };

            // Set up cleanup on close
            transport.onclose = () => {
                console.log(`[${new Date().toISOString()}] Session closed: ${sessionId}`);
                sessions.delete(sessionId);
            };

            // Connect the transport to the server
            await server.connect(transport);

            // Store the session
            session = { server, transport, apiKey: apiKey as string };
            sessions.set(sessionId, session);
        } else if (session.apiKey !== apiKey) {
            // API key changed - recreate session
            console.log(`[${new Date().toISOString()}] API key changed for session ${sessionId}, recreating...`);
            session.transport.close();
            sessions.delete(sessionId);

            // Create new session with new API key
            const server = createMcpServer(apiKey as string);
            const transport = new StreamableHTTPServerTransport({
                sessionIdGenerator: () => sessionId
            });

            await server.connect(transport);
            session = { server, transport, apiKey: apiKey as string };
            sessions.set(sessionId, session);
        }

        // Handle the request with the session's transport
        await session.transport.handleRequest(req, res, req.body);

    } catch (error) {
        console.error(`[${new Date().toISOString()}] Error handling MCP request:`, error);
        if (!res.headersSent) {
            res.status(500).json({
                jsonrpc: '2.0',
                error: {
                    code: -32603,
                    message: 'Internal server error',
                },
                id: req.body.id || null
            });
        }
    }
});

// DELETE endpoint for session termination
app.delete('/mcp', (req, res) => {
    const sessionId = req.headers['mcp-session-id'] as string;

    if (!sessionId) {
        res.status(400).json({
            jsonrpc: '2.0',
            error: {
                code: -32000,
                message: 'Bad Request: No session ID provided',
            },
            id: null
        });
        return;
    }

    // Close the session if it exists
    const session = sessions.get(sessionId);
    if (session) {
        console.log(`[${new Date().toISOString()}] Terminating session: ${sessionId}`);
        session.transport.close();
        sessions.delete(sessionId);
    }

    res.status(200).json({
        jsonrpc: '2.0',
        result: {
            message: session ? 'Session terminated successfully' : 'Session not found (may have already been closed)'
        },
        id: null
    });
});

// Error handling middleware
app.use((error: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
    console.error(`[${new Date().toISOString()}] Unhandled error:`, error);
    if (!res.headersSent) {
        res.status(500).json({
            jsonrpc: '2.0',
            error: {
                code: -32603,
                message: 'Internal server error',
            },
            id: null
        });
    }
});

// Start server
const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
    const collection = process.env.AIRWEAVE_COLLECTION || 'default';
    const baseUrl = process.env.AIRWEAVE_BASE_URL || 'https://api.airweave.ai';

    console.log(`🚀 Airweave MCP Search Server (Streamable HTTP) started`);
    console.log(`📡 Protocol: MCP 2025-03-26`);
    console.log(`🔗 Endpoint: http://localhost:${PORT}/mcp`);
    console.log(`🏥 Health: http://localhost:${PORT}/health`);
    console.log(`📋 Info: http://localhost:${PORT}/`);
    console.log(`📚 Collection: ${collection}`);
    console.log(`🌐 Base URL: ${baseUrl}`);
    console.log(`\n🔑 Authentication required: Provide your Airweave API key via:`);
    console.log(`   - Authorization: Bearer <your-api-key>`);
    console.log(`   - X-API-Key: <your-api-key>`);
    console.log(`   - Query parameter: ?apiKey=your-key`);
});