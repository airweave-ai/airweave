#!/usr/bin/env node

/**
 * Airweave MCP Server - HTTP/Streamable Transport with Redis Session Management
 * 
 * This is the production HTTP server for cloud-based AI platforms like OpenAI Agent Builder.
 * Uses the modern Streamable HTTP transport (MCP 2025-03-26) instead of deprecated SSE.
 * 
 * Session Management:
 * - Redis stores session metadata (API key, collection, timestamps)
 * - Each pod maintains an in-memory cache of McpServer/Transport instances
 * - Sessions can be served by any pod (stateless, horizontally scalable)
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
import { RedisSessionManager, SessionData, SessionWithTransport, SessionMetadata } from './session/redis-session-manager.js';

const app = express();
app.use(express.json({ limit: '10mb' }));

// Initialize Redis session manager
const sessionManager = new RedisSessionManager();

// Create MCP server instance with tools
const createMcpServer = (apiKey: string, collection: string) => {
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
app.get('/health', async (req, res) => {
    const redisConnected = sessionManager.isConnected();

    res.json({
        status: redisConnected ? 'healthy' : 'degraded',
        transport: 'streamable-http',
        protocol: 'MCP 2025-03-26',
        collection: process.env.AIRWEAVE_COLLECTION || 'unknown',
        redis: {
            connected: redisConnected
        },
        timestamp: new Date().toISOString()
    });
});

// Root endpoint with server info
app.get('/', (req, res) => {
    const defaultCollection = process.env.AIRWEAVE_COLLECTION || 'default';
    const baseUrl = process.env.AIRWEAVE_BASE_URL || 'https://api.airweave.ai';

    res.json({
        name: "Airweave MCP Search Server",
        version: "2.1.0",
        transport: "Streamable HTTP",
        protocol: "MCP 2025-03-26",
        collection: defaultCollection + " (default, override with X-Collection-Readable-ID header)",
        endpoints: {
            health: "/health",
            mcp: "/mcp"
        },
        authentication: {
            required: true,
            methods: [
                "X-API-Key: <your-api-key> (recommended)",
                "Authorization: Bearer <your-api-key>",
                "Query parameter: ?apiKey=your-key",
                "Query parameter: ?api_key=your-key"
            ],
            headers: {
                "X-API-Key": "Your Airweave API key (required)",
                "X-Collection-Readable-ID": "Collection readable ID to search (optional, falls back to default)"
            },
            openai_agent_builder: {
                url: "https://mcp.airweave.ai/mcp",
                headers: {
                    "X-API-Key": "<your-airweave-api-key>",
                    "X-Collection-Readable-ID": "<your-collection-readable-id>"
                }
            }
        }
    });
});

// Local cache: Map session IDs to { server, transport, data }
// This cache is per-pod and reconstructed from Redis as needed
const localSessionCache = new Map<string, SessionWithTransport>();

/**
 * Helper function to create or recreate session objects (server + transport)
 * Note: apiKey parameter is the PLAINTEXT key needed for API calls
 */
async function createSessionObjects(sessionData: SessionData, apiKey: string): Promise<SessionWithTransport> {
    const { sessionId, collection, baseUrl } = sessionData;

    // Create a new server with the API key and collection
    const server = createMcpServer(apiKey, collection);

    // Create a new transport for this session
    const transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => sessionId
    });

    // Set up session management callbacks
    (transport as any).onsessioninitialized = (sid: string) => {
        console.log(`[${new Date().toISOString()}] Session initialized: ${sid}`);
    };

    // Set up cleanup on close
    transport.onclose = async () => {
        console.log(`[${new Date().toISOString()}] Session closed: ${sessionId}`);
        localSessionCache.delete(sessionId);
        await sessionManager.deleteSession(sessionId);
    };

    // Connect the transport to the server
    await server.connect(transport);

    return { server, transport, data: sessionData };
}

// Main MCP endpoint (Streamable HTTP) with Redis session management
app.post('/mcp', async (req, res) => {
    try {
        // Extract API key from request headers or query parameters
        const apiKey = req.headers['x-api-key'] ||
            req.headers['authorization']?.replace('Bearer ', '') ||
            req.query.apiKey ||
            req.query.api_key;

        // Extract collection from custom header (supports multi-tenancy)
        const collectionId = req.headers['x-collection-readable-id'] as string ||
            process.env.AIRWEAVE_COLLECTION ||
            'default';

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
        const sessionId = req.headers['mcp-session-id'] as string ||
            `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        const baseUrl = process.env.AIRWEAVE_BASE_URL || 'https://api.airweave.ai';

        // Security: Extract client metadata for session binding
        const clientIP = (req.headers['x-forwarded-for'] as string)?.split(',')[0] ||
            (req.headers['x-real-ip'] as string) ||
            req.socket.remoteAddress ||
            'unknown';
        const userAgent = req.headers['user-agent'] || 'unknown';

        let session: SessionWithTransport | undefined;

        // Step 1: Check local cache (fastest path - same pod, same session)
        session = localSessionCache.get(sessionId);

        if (session) {
            // Security: Validate API key hasn't changed
            const apiKeyMatches = RedisSessionManager.validateApiKey(
                apiKey as string,
                session.data.apiKeyHash
            );

            if (!apiKeyMatches) {
                console.log(`[${new Date().toISOString()}] API key changed for session ${sessionId}, recreating...`);

                // Close old session
                session.transport.close();
                localSessionCache.delete(sessionId);

                // Create new session data with hash
                const newSessionData: SessionData = {
                    sessionId,
                    apiKeyHash: RedisSessionManager.hashApiKey(apiKey as string),
                    collection: collectionId,
                    baseUrl,
                    createdAt: Date.now(),
                    lastAccessedAt: Date.now(),
                    clientIP,
                    userAgent
                };

                // Store in Redis
                await sessionManager.setSession(newSessionData, true);

                // Create new session objects
                session = await createSessionObjects(newSessionData, apiKey as string);
                localSessionCache.set(sessionId, session);
            } else {
                // Security: Validate session binding
                // NOTE: Disabled for cloud platforms (OpenAI Agent Builder) that use load balancers
                // Multiple IPs from the same client are expected in production
                if (session.data.clientIP && session.data.clientIP !== clientIP) {
                    console.warn(`[${new Date().toISOString()}] IP changed for session ${sessionId} (load balancer): ${session.data.clientIP} -> ${clientIP}`);
                    // Allow the request to proceed - cloud platforms use load balancers
                }
            }
        } else {
            // Step 2: Not in local cache - check Redis (different pod or first request)
            const sessionData = await sessionManager.getSession(sessionId);

            if (sessionData) {
                // Session exists in Redis but not in this pod's cache
                console.log(`[${new Date().toISOString()}] Restoring session from Redis: ${sessionId}`);

                // Security: Validate API key matches
                const apiKeyMatches = RedisSessionManager.validateApiKey(
                    apiKey as string,
                    sessionData.apiKeyHash
                );

                if (!apiKeyMatches) {
                    console.log(`[${new Date().toISOString()}] API key mismatch for session ${sessionId}, recreating...`);

                    // Update session data with new API key hash
                    sessionData.apiKeyHash = RedisSessionManager.hashApiKey(apiKey as string);
                    sessionData.lastAccessedAt = Date.now();
                    sessionData.clientIP = clientIP;
                    sessionData.userAgent = userAgent;
                    await sessionManager.setSession(sessionData, false);
                }

                // Security: Validate session binding
                // NOTE: Disabled for cloud platforms (OpenAI Agent Builder) that use load balancers
                // Multiple IPs from the same client are expected in production
                if (sessionData.clientIP && sessionData.clientIP !== clientIP) {
                    console.warn(`[${new Date().toISOString()}] IP changed for session ${sessionId} (load balancer): ${sessionData.clientIP} -> ${clientIP}`);
                    // Allow the request to proceed - cloud platforms use load balancers
                }

                // Recreate server and transport from session data
                session = await createSessionObjects(sessionData, apiKey as string);
                localSessionCache.set(sessionId, session);
            } else {
                // Step 3: New session - check rate limit first
                console.log(`[${new Date().toISOString()}] Creating new session: ${sessionId}`);

                // Security: Check rate limit
                const rateLimit = await sessionManager.checkRateLimit(apiKey as string);
                if (!rateLimit.allowed) {
                    console.warn(`[${new Date().toISOString()}] Rate limit exceeded for API key (${rateLimit.count} sessions/hour)`);
                    res.status(429).json({
                        jsonrpc: '2.0',
                        error: {
                            code: -32002,
                            message: 'Too many sessions created. Please try again later.',
                            data: {
                                limit: 100,
                                current: rateLimit.count,
                                retryAfter: 3600
                            }
                        },
                        id: req.body.id || null
                    });
                    return;
                }

                const newSessionData: SessionData = {
                    sessionId,
                    apiKeyHash: RedisSessionManager.hashApiKey(apiKey as string),
                    collection: collectionId,
                    baseUrl,
                    createdAt: Date.now(),
                    lastAccessedAt: Date.now(),
                    clientIP,
                    userAgent
                };

                // Store in Redis
                await sessionManager.setSession(newSessionData, true);

                // Create session objects
                session = await createSessionObjects(newSessionData, apiKey as string);
                localSessionCache.set(sessionId, session);
            }
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
app.delete('/mcp', async (req, res) => {
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

    // Close the session if it exists locally
    const session = localSessionCache.get(sessionId);
    if (session) {
        console.log(`[${new Date().toISOString()}] Terminating session: ${sessionId}`);
        session.transport.close();
        localSessionCache.delete(sessionId);
    }

    // Delete from Redis (works across all pods)
    await sessionManager.deleteSession(sessionId);

    res.status(200).json({
        jsonrpc: '2.0',
        result: {
            message: 'Session terminated successfully'
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

// Initialize and start server
async function startServer() {
    const PORT = process.env.PORT || 8080;
    const collection = process.env.AIRWEAVE_COLLECTION || 'default';
    const baseUrl = process.env.AIRWEAVE_BASE_URL || 'https://api.airweave.ai';

    try {
        // Connect to Redis
        console.log('🔌 Connecting to Redis...');
        await sessionManager.connect();
        console.log('✅ Redis connected');

        // Start HTTP server
        const server = app.listen(PORT, () => {
            console.log(`\n🚀 Airweave MCP Search Server (Streamable HTTP) started`);
            console.log(`📡 Protocol: MCP 2025-03-26`);
            console.log(`🔗 Endpoint: http://localhost:${PORT}/mcp`);
            console.log(`🏥 Health: http://localhost:${PORT}/health`);
            console.log(`📋 Info: http://localhost:${PORT}/`);
            console.log(`📚 Collection: ${collection}`);
            console.log(`🌐 Base URL: ${baseUrl}`);
            console.log(`💾 Session Storage: Redis (stateless, horizontally scalable)`);
            console.log(`\n🔑 Authentication required: Provide your Airweave API key via:`);
            console.log(`   - Authorization: Bearer <your-api-key>`);
            console.log(`   - X-API-Key: <your-api-key>`);
            console.log(`   - Query parameter: ?apiKey=your-key`);
        });

        // Graceful shutdown
        const shutdown = async (signal: string) => {
            console.log(`\n${signal} received. Shutting down gracefully...`);

            // Close HTTP server
            server.close(() => {
                console.log('HTTP server closed');
            });

            // Close all local sessions
            console.log(`Closing ${localSessionCache.size} local sessions...`);
            for (const [sessionId, session] of localSessionCache.entries()) {
                try {
                    session.transport.close();
                } catch (err) {
                    console.error(`Error closing session ${sessionId}:`, err);
                }
            }
            localSessionCache.clear();

            // Disconnect from Redis
            await sessionManager.disconnect();
            console.log('Redis disconnected');

            process.exit(0);
        };

        process.on('SIGTERM', () => shutdown('SIGTERM'));
        process.on('SIGINT', () => shutdown('SIGINT'));

    } catch (error) {
        console.error('Failed to start server:', error);
        process.exit(1);
    }
}

// Start the server
startServer().catch(console.error);