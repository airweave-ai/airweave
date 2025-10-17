#!/usr/bin/env node

// HTTP/SSE entry point for the Airweave MCP Search Server
// This version is designed to be deployed as a service for cloud-based AI assistants

import express, { Request, Response } from "express";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { createMcpServer, validateHttpEnvironment } from "./server.js";

// Validate environment variables and get configuration
// Note: API key comes from client, not server environment
const config = validateHttpEnvironment();

// Get port from environment or default to 8080
const PORT = process.env.PORT || 8080;

// Create Express app
const app = express();

// Health check endpoint
app.get("/health", (_req: Request, res: Response) => {
    res.json({
        status: "healthy",
        collection: config.collection,
        baseUrl: config.baseUrl,
        timestamp: new Date().toISOString(),
    });
});

// Root endpoint with server info
app.get("/", (_req: Request, res: Response) => {
    res.json({
        name: "Airweave MCP Search Server",
        version: "2.1.0",
        collection: config.collection,
        transport: "SSE",
        endpoints: {
            health: "/health",
            sse: "/sse",
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
                url: "https://mcp.dev-airweave.com/sse",
                headers: {
                    Authorization: "Bearer <your-airweave-api-key>"
                }
            },
            instructions: "Provide your Airweave API key using one of the methods above when connecting to /sse"
        },
    });
});

// SSE endpoint for MCP protocol
app.get("/sse", async (req: Request, res: Response) => {
    console.error(`[${new Date().toISOString()}] New SSE connection from ${req.ip}`);

    // Extract API key from request headers or query parameters
    const apiKey =
        req.headers['x-api-key'] as string ||
        req.headers['authorization']?.replace('Bearer ', '') ||
        req.query.apiKey as string ||
        req.query.api_key as string;

    if (!apiKey) {
        console.error(`[${new Date().toISOString()}] Missing API key in SSE request`);
        res.status(401).json({
            error: "Authentication required",
            message: "Please provide an API key via X-API-Key header, Authorization header, or apiKey query parameter"
        });
        return;
    }

    // Create full config with client's API key
    const fullConfig = {
        ...config,
        apiKey
    };

    // Create a new MCP server instance for this connection
    const server = createMcpServer(fullConfig);

    // Create SSE transport
    const transport = new SSEServerTransport("/message", res);

    // Connect server to transport
    await server.connect(transport);

    console.error(`[${new Date().toISOString()}] MCP server connected via SSE`);

    // Handle connection close
    req.on("close", () => {
        console.error(`[${new Date().toISOString()}] SSE connection closed`);
    });
});

// POST endpoint for client messages (required by SSE transport)
app.post("/message", express.json(), async (req: Request, res: Response) => {
    // The SSE transport handles this internally
    // This endpoint is registered but the actual handling is done by the transport
    res.status(200).send();
});

// Error handling middleware
app.use((err: Error, _req: Request, res: Response, _next: any) => {
    console.error("Server error:", err);
    res.status(500).json({ error: "Internal server error" });
});

// Start the server
app.listen(PORT, () => {
    console.error(`Airweave MCP Search Server (HTTP/SSE) started`);
    console.error(`Collection: ${config.collection}`);
    console.error(`Base URL: ${config.baseUrl}`);
    console.error(`Listening on port: ${PORT}`);
    console.error(`SSE endpoint: http://localhost:${PORT}/sse`);
});

// Handle graceful shutdown
process.on("SIGINT", () => {
    console.error("Shutting down Airweave MCP HTTP server...");
    process.exit(0);
});

process.on("SIGTERM", () => {
    console.error("Shutting down Airweave MCP HTTP server...");
    process.exit(0);
});

