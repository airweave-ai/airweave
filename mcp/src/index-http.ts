#!/usr/bin/env node

/**
 * Airweave MCP Server - HTTP/Streamable Transport with Redis Session Management
 * 
 * This is the production HTTP server for cloud-based AI platforms like OpenAI Agent Builder.
 * Uses the modern Streamable HTTP transport (MCP 2025-03-26) instead of deprecated SSE.
 * 
 * Features:
 * - Redis-based distributed session storage (stateless, horizontally scalable)
 * - Dynamic multi-collection discovery (auto-registers tools per API key)
 * - Session security (IP binding, API key hashing, rate limiting)
 * 
 * Session Management:
 * - Redis stores session metadata (API key hash, collection, timestamps, client metadata)
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
import { RedisSessionManager, SessionData, SessionWithTransport } from './session/redis-session-manager.js';

const app = express();
app.use(express.json({ limit: '10mb' }));

// Initialize Redis session manager
const sessionManager = new RedisSessionManager();

// Local cache: Map session IDs to { server, transport, data }
// This cache is per-pod and reconstructed from Redis as needed
const localSessionCache = new Map<string, SessionWithTransport>();

// Fetch collections from Airweave API
async function fetchCollections(apiKey: string, baseUrl: string): Promise<any[]> {
    try {
        const response = await fetch(`${baseUrl}/collections?limit=100`, {
            headers: {
                'X-API-Key': apiKey
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const collections = await response.json();
        console.log(`[${new Date().toISOString()}] Fetched ${collections.length} collections for API key`);
        return collections;
    } catch (error) {
        console.error(`[${new Date().toISOString()}] Failed to fetch collections:`, error);
        throw error;
    }
}

// Create MCP server instance with tools dynamically based on available collections
async function createMcpServer(apiKey: string): Promise<McpServer> {
    const baseUrl = process.env.AIRWEAVE_BASE_URL || 'https://api.airweave.ai';
    const fallbackCollection = process.env.AIRWEAVE_COLLECTION || 'default';

    const server = new McpServer({
        name: 'airweave-search',
        version: '2.1.0',
    }, {
        capabilities: {
            tools: {},
            logging: {}
        }
    });

    try {
        // Fetch all collections for this API key
        const collections = await fetchCollections(apiKey, baseUrl);
        const searchToolNames: string[] = [];

        if (collections.length === 0) {
            console.warn(`[${new Date().toISOString()}] No collections found, using fallback collection: ${fallbackCollection}`);
            // Fallback: create single tool with default collection
            const config = { collection: fallbackCollection, baseUrl, apiKey };
            const airweaveClient = new AirweaveClient(config);
            const searchTool = createSearchTool(`search-${fallbackCollection}`, fallbackCollection, airweaveClient);
            server.tool(searchTool.name, searchTool.description, searchTool.schema, searchTool.handler);
            searchToolNames.push(searchTool.name);
        } else {
            // Register one search tool per collection
            console.log(`[${new Date().toISOString()}] Registering tools for ${collections.length} collections`);

            for (const collection of collections) {
                const config = {
                    collection: collection.readable_id,
                    baseUrl,
                    apiKey
                };

                const airweaveClient = new AirweaveClient(config);
                const toolName = `search-${collection.readable_id}`;

                // Create enhanced tool description with collection metadata
                const searchTool = createSearchTool(toolName, collection.readable_id, airweaveClient);

                // Enhance the description with collection name and status
                const enhancedDescription = `Search within the '${collection.name}' collection (${collection.readable_id}).

Status: ${collection.status || 'unknown'}
Last updated: ${collection.modified_at ? new Date(collection.modified_at).toLocaleString() : 'unknown'}

${searchTool.description}`;

                server.tool(
                    searchTool.name,
                    enhancedDescription,
                    searchTool.schema,
                    searchTool.handler
                );

                searchToolNames.push(searchTool.name);
                console.log(`[${new Date().toISOString()}] Registered tool: ${toolName} for collection: ${collection.name}`);
            }
        }

        // Register the config tool (shows all collections) - pass actual search tool names
        const configTool = createConfigTool(searchToolNames, fallbackCollection, baseUrl, apiKey);
        server.tool(configTool.name, configTool.description, configTool.schema, configTool.handler);

    } catch (error) {
        console.error(`[${new Date().toISOString()}] Failed to fetch collections, using fallback:`, error);

        // Fallback: create single tool with default collection
        const config = { collection: fallbackCollection, baseUrl, apiKey };
        const airweaveClient = new AirweaveClient(config);
        const searchTool = createSearchTool(`search-${fallbackCollection}`, fallbackCollection, airweaveClient);
        const configTool = createConfigTool([searchTool.name], fallbackCollection, baseUrl, apiKey);

        server.tool(searchTool.name, searchTool.description, searchTool.schema, searchTool.handler);
        server.tool(configTool.name, configTool.description, configTool.schema, configTool.handler);
    }

    return server;
}

/**
 * Helper function to create or recreate session objects (server + transport)
 * Note: apiKey parameter is the PLAINTEXT key needed for API calls and collection discovery
 */
async function createSessionObjects(sessionData: SessionData, apiKey: string): Promise<SessionWithTransport> {
    const { sessionId } = sessionData;

    // Create a new server with the API key (async - fetches collections)
    const server = await createMcpServer(apiKey);

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

// Health check endpoint
app.get('/health', async (req, res) => {
    const redisConnected = sessionManager.isConnected();

    res.json({
        status: redisConnected ? 'healthy' : 'degraded',
        transport: 'streamable-http',
        protocol: 'MCP 2025-03-26',
        mode: 'multi-collection',
        active_sessions: localSessionCache.size,
        redis: {
            connected: redisConnected
        },
        timestamp: new Date().toISOString()
    });
});

// Root endpoint with server info
app.get('/', (req, res) => {
    const baseUrl = process.env.AIRWEAVE_BASE_URL || 'https://api.airweave.ai';

    res.json({
        name: "Airweave MCP Search Server",
        version: "2.1.0",
        transport: "Streamable HTTP",
        protocol: "MCP 2025-03-26",
        mode: "multi-collection",
        description: "Dynamically discovers and provides search tools for all collections accessible via your API key",
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
            },
            notes: "Each API key gets access to its organization's collections. Tools are dynamically registered per session."
        },
        session_storage: {
            type: "redis",
            features: ["distributed", "stateless", "horizontally-scalable", "session-binding", "rate-limiting"]
        }
    });
});

// Main MCP endpoint (Streamable HTTP) with Redis session management
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
        const sessionId = req.headers['mcp-session-id'] as string ||
            `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        const collection = process.env.AIRWEAVE_COLLECTION || 'default';
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
                    collection,
                    baseUrl,
                    createdAt: Date.now(),
                    lastAccessedAt: Date.now(),
                    clientIP,
                    userAgent
                };

                // Store in Redis
                await sessionManager.setSession(newSessionData, true);

                // Create new session objects (async - discovers collections)
                session = await createSessionObjects(newSessionData, apiKey as string);
                localSessionCache.set(sessionId, session);
            } else {
                // Security: Validate session binding
                if (session.data.clientIP && session.data.clientIP !== clientIP) {
                    console.warn(`[${new Date().toISOString()}] Session hijacking attempt detected: IP mismatch for ${sessionId}`);
                    res.status(403).json({
                        jsonrpc: '2.0',
                        error: {
                            code: -32003,
                            message: 'Session validation failed: Client identity mismatch',
                        },
                        id: req.body.id || null
                    });
                    return;
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
                if (sessionData.clientIP && sessionData.clientIP !== clientIP) {
                    console.warn(`[${new Date().toISOString()}] Session hijacking attempt detected: IP mismatch for ${sessionId}`);
                    res.status(403).json({
                        jsonrpc: '2.0',
                        error: {
                            code: -32003,
                            message: 'Session validation failed: Client identity mismatch',
                        },
                        id: req.body.id || null
                    });
                    return;
                }

                // Recreate server and transport from session data (async - discovers collections)
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
                    collection,
                    baseUrl,
                    createdAt: Date.now(),
                    lastAccessedAt: Date.now(),
                    clientIP,
                    userAgent
                };

                // Store in Redis
                await sessionManager.setSession(newSessionData, true);

                // Create session objects (async - discovers collections)
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
            console.log(`🔄 Mode: Multi-collection (dynamically discovers collections per API key)`);
            console.log(`🌐 Base URL: ${baseUrl}`);
            console.log(`💾 Session Storage: Redis (stateless, horizontally scalable)`);
            console.log(`\n🔑 Authentication required: Provide your Airweave API key via:`);
            console.log(`   - Authorization: Bearer <your-api-key>`);
            console.log(`   - X-API-Key: <your-api-key>`);
            console.log(`   - Query parameter: ?apiKey=your-key`);
            console.log(`\n✨ Each API key gets search tools for all accessible collections`);
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
