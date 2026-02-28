#!/usr/bin/env node

/**
 * Airweave MCP Server - Stateless HTTP/Streamable Transport
 *
 * Production HTTP server for cloud-based AI platforms like OpenAI Agent Builder.
 * Uses the modern Streamable HTTP transport (MCP 2025-03-26).
 *
 * Fully stateless: a fresh McpServer + transport is created per request.
 * Authentication is per-request via headers. No sessions, no Redis.
 *
 * Endpoint: https://mcp.airweave.ai/mcp
 * Protocol: MCP 2025-03-26 (Streamable HTTP)
 * Authentication: X-API-Key or Bearer token
 */

import express from 'express';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { mcpAuthRouter } from '@modelcontextprotocol/sdk/server/auth/router.js';
import type { AuthInfo } from '@modelcontextprotocol/sdk/server/auth/types.js';
import { createMcpServer, VERSION } from './server.js';
import { AirweaveConfig } from './api/types.js';
import { DEFAULT_BASE_URL } from './config/constants.js';
import { initPostHog, shutdownPostHog, trackMcpRequest, trackMcpError } from './analytics/posthog.js';
import { resolveOrganizationForCollection } from './api/org-resolver.js';
import { Auth0OAuthProvider } from './auth/auth0-provider.js';
import { createAuth0CallbackHandler } from './auth/auth0-callback.js';
import { ensureRedisReady } from './auth/redis.js';

const app = express();
app.set('trust proxy', 1);
app.use(express.json({ limit: '10mb' }));

const oauthEnabled = process.env.MCP_OAUTH_ENABLED === 'true';
let auth0Provider: Auth0OAuthProvider | null = null;

if (oauthEnabled) {
    auth0Provider = new Auth0OAuthProvider();
    const baseUrl = new URL(process.env.MCP_BASE_URL || 'https://mcp.airweave.ai');

    app.use(
        mcpAuthRouter({
            provider: auth0Provider,
            issuerUrl: baseUrl,
            baseUrl,
            scopesSupported: ['openid', 'profile', 'email', 'offline_access'],
            resourceName: 'Airweave MCP',
        })
    );

    app.get('/oauth/callback', createAuth0CallbackHandler(auth0Provider));
}

/**
 * Extract Bearer token per RFC 6750.
 * RFC 7235 Section 2.1 / RFC 9110 Section 11.1: auth scheme is case-insensitive.
 */
function extractBearerToken(header: string | undefined): string | undefined {
    if (!header || header.length < 8) return undefined;
    if (header.slice(0, 7).toLowerCase() !== 'bearer ') return undefined;
    return header.slice(7);
}

/**
 * Extract API key from request headers.
 */
function extractApiKey(req: express.Request): string | undefined {
    return (req.headers['x-api-key'] as string) ||
        extractBearerToken(req.headers['authorization'] as string) ||
        undefined;
}

function extractMcpCredential(req: express.Request & { auth?: AuthInfo }): string | undefined {
    return req.auth?.token || extractApiKey(req);
}

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        transport: 'streamable-http',
        protocol: 'MCP 2025-03-26',
        mode: 'stateless',
        version: VERSION,
        timestamp: new Date().toISOString()
    });
});

// Root endpoint with server info
app.get('/', (req, res) => {
    res.json({
        name: "Airweave MCP Search Server",
        version: VERSION,
        transport: "Streamable HTTP",
        protocol: "MCP 2025-03-26",
        mode: "stateless",
        endpoints: {
            health: "/health",
            mcp: "/mcp"
        },
        authentication: {
            required: true,
            methods: [
                "X-API-Key: <your-api-key> (recommended)",
                "Authorization: Bearer <your-api-key-or-oauth-token>"
            ],
            headers: {
                "X-API-Key": "Your Airweave API key (required)",
                "X-Collection-Readable-ID": "Collection readable ID to search (optional, falls back to env default)"
            },
            openai_agent_builder: {
                url: "https://mcp.airweave.ai/mcp",
                headers: {
                    "X-API-Key": "<your-airweave-api-key>",
                    "X-Collection-Readable-ID": "<your-collection-readable-id>"
                }
            },
            oauth: oauthEnabled ? {
                enabled: true,
                discovery: "/.well-known/oauth-authorization-server",
                callback: "/oauth/callback"
            } : { enabled: false }
        }
    });
});

// Main MCP endpoint - fully stateless, fresh server per request
app.post('/mcp', async (req: express.Request & { auth?: AuthInfo }, res) => {
    const startTime = Date.now();

    try {
        const apiKey = extractMcpCredential(req);

        if (!apiKey) {
            trackMcpError(undefined, {
                errorCode: -32001,
                errorMessage: 'Authentication required'
            });
            res.status(401).json({
                jsonrpc: '2.0',
                error: {
                    code: -32001,
                    message: 'Authentication required',
                    data: 'Please provide API key or complete OAuth authorization flow'
                },
                id: req.body?.id || null
            });
            return;
        }

        const collection = (req.headers['x-collection-readable-id'] as string) ||
            process.env.AIRWEAVE_COLLECTION ||
            'default';
        const baseUrl = process.env.AIRWEAVE_BASE_URL || DEFAULT_BASE_URL;
        const method = req.body?.method || 'unknown';

        let organizationId: string | undefined;
        if (req.auth?.token) {
            try {
                organizationId = await resolveOrganizationForCollection(apiKey, baseUrl, collection);
            } catch (err) {
                console.error(`[${new Date().toISOString()}] Org resolution failed:`, err);
                res.status(400).json({
                    jsonrpc: '2.0',
                    error: {
                        code: -32002,
                        message: err instanceof Error ? err.message : 'Organization resolution failed',
                    },
                    id: req.body?.id || null
                });
                return;
            }
        }

        const config: AirweaveConfig = { apiKey, collection, baseUrl, organizationId };
        const server = createMcpServer(config);

        const transport = new StreamableHTTPServerTransport({
            sessionIdGenerator: undefined
        });

        await server.connect(transport);
        await transport.handleRequest(req as express.Request & { auth?: AuthInfo }, res, req.body);

        trackMcpRequest(apiKey, {
            method,
            collection,
            responseTimeMs: Date.now() - startTime
        });

        // Clean up after the response is sent
        res.on('close', async () => {
            try {
                await transport.close();
                await server.close();
            } catch (err) {
                console.error(`[${new Date().toISOString()}] Error during cleanup:`, err);
            }
        });

    } catch (error) {
        console.error(`[${new Date().toISOString()}] Error handling MCP request:`, error);
        trackMcpError(extractApiKey(req), {
            errorCode: -32603,
            errorMessage: error instanceof Error ? error.message : 'Internal server error'
        });
        if (!res.headersSent) {
            res.status(500).json({
                jsonrpc: '2.0',
                error: {
                    code: -32603,
                    message: 'Internal server error',
                },
                id: req.body?.id || null
            });
        }
    }
});

// DELETE endpoint - no-op in stateless mode, return success for protocol compliance
app.delete('/mcp', (req, res) => {
    res.status(200).json({
        jsonrpc: '2.0',
        result: { message: 'Session terminated (stateless mode)' },
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
async function startServer() {
    const PORT = process.env.PORT || 8080;
    const collection = process.env.AIRWEAVE_COLLECTION || 'default';
    const baseUrl = process.env.AIRWEAVE_BASE_URL || DEFAULT_BASE_URL;

    if (oauthEnabled) {
        await ensureRedisReady();
    }

    initPostHog();

    const server = app.listen(PORT, () => {
        console.log(`Airweave MCP Search Server v${VERSION} (Streamable HTTP) started`);
        console.log(`Protocol: MCP 2025-03-26 | Mode: stateless`);
        console.log(`Endpoint: http://localhost:${PORT}/mcp`);
        console.log(`Health: http://localhost:${PORT}/health`);
        console.log(`Default collection: ${collection} | Base URL: ${baseUrl}`);
        if (oauthEnabled) {
            console.log('OAuth enabled with mcpAuthRouter');
        }
    });

    const shutdown = async (signal: string) => {
        console.log(`${signal} received. Shutting down...`);
        await shutdownPostHog();
        server.close(() => {
            console.log('HTTP server closed');
            process.exit(0);
        });
    };

    process.on('SIGTERM', () => shutdown('SIGTERM'));
    process.on('SIGINT', () => shutdown('SIGINT'));
}

startServer().catch((error) => {
    console.error('Failed to start server:', error);
    process.exit(1);
});
