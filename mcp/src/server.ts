// MCP server setup and tool registration

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { AirweaveClient } from "./api/airweave-client.js";
import { AirweaveConfig } from "./api/types.js";
import { createSearchTool } from "./tools/search-tool.js";
import { createConfigTool } from "./tools/config-tool.js";
import { DEFAULT_BASE_URL, ERROR_MESSAGES, VERSION } from "./config/constants.js";

export { VERSION };

export function createMcpServer(config: AirweaveConfig) {
    const server = new McpServer({
        name: "airweave-search",
        version: VERSION,
    }, {
        capabilities: {
            tools: {},
            logging: {}
        }
    });

    const toolName = `search-${config.collection}`;
    const airweaveClient = new AirweaveClient(config);
    const searchTool = createSearchTool(toolName, config.collection, airweaveClient);
    const configTool = createConfigTool(toolName, config.collection, config.baseUrl, config.apiKey);

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
}

export function validateEnvironment(): AirweaveConfig {
    const apiKey = process.env.AIRWEAVE_API_KEY;
    const collection = process.env.AIRWEAVE_COLLECTION;
    const baseUrl = process.env.AIRWEAVE_BASE_URL || DEFAULT_BASE_URL;

    if (!apiKey) {
        console.error(ERROR_MESSAGES.MISSING_API_KEY);
        process.exit(1);
    }

    if (!collection) {
        console.error(ERROR_MESSAGES.MISSING_COLLECTION);
        process.exit(1);
    }

    return { apiKey, collection, baseUrl };
}
