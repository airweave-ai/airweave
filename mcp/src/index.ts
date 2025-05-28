#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// Environment variables configuration
const AIRWEAVE_API_KEY = process.env.AIRWEAVE_API_KEY;
const AIRWEAVE_COLLECTION = process.env.AIRWEAVE_COLLECTION;
const AIRWEAVE_BASE_URL = process.env.AIRWEAVE_BASE_URL || "https://api.airweave.ai";

// Validate required environment variables
if (!AIRWEAVE_API_KEY) {
  console.error("Error: AIRWEAVE_API_KEY environment variable is required");
  process.exit(1);
}

if (!AIRWEAVE_COLLECTION) {
  console.error("Error: AIRWEAVE_COLLECTION environment variable is required");
  process.exit(1);
}

// Create MCP server instance
const server = new McpServer({
  name: "airweave-search",
  version: "1.0.7",
  capabilities: {
    tools: {},
  },
});

// Create dynamic tool name based on collection
const toolName = `search-${AIRWEAVE_COLLECTION}`;

// Types for Airweave API responses
interface SearchResponse {
  results: Record<string, any>[];
  response_type: string;
  completion?: string;
  status: string;
}

// Helper function to make requests to Airweave API
async function makeAirweaveRequest(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const url = `${AIRWEAVE_BASE_URL}${endpoint}`;

  const headers = {
    "x-api-key": AIRWEAVE_API_KEY!,
    "Content-Type": "application/json",
    "Accept": "application/json",
    ...options.headers,
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Airweave API error (${response.status}): ${errorText}`);
  }

  return response;
}

// Register the search tool
server.tool(
  toolName,
  `Search within the Airweave collection '${AIRWEAVE_COLLECTION}'`,
  {
    query: z.string().min(1).describe("The search query to execute"),
    response_type: z
      .enum(["raw", "completion"])
      .optional()
      .default("raw")
      .describe("Type of response: raw for search results, completion for AI-generated response"),
  },
  async ({ query, response_type = "raw" }) => {
    try {
      // Construct the search endpoint URL
      const endpoint = `/collections/${AIRWEAVE_COLLECTION}/search`;
      const searchParams = new URLSearchParams({
        query,
        response_type,
      });

      // Make the request to Airweave
      const response = await makeAirweaveRequest(
        `${endpoint}?${searchParams.toString()}`,
        {
          method: "GET",
        }
      );

      const responseText = await response.text();
      let searchResponse: SearchResponse;

      try {
        searchResponse = JSON.parse(responseText);
      } catch (parseError) {
        console.error("Failed to parse JSON response:", responseText.substring(0, 500));
        throw new Error(`Invalid JSON response: ${responseText.substring(0, 200)}...`);
      }

      // Format the response based on type
      if (response_type === "completion") {
        // For AI completion, return the completion text
        return {
          content: [
            {
              type: "text",
              text: searchResponse.completion || "No response generated",
            },
          ],
        };
      } else {
        // For raw results, format the search results simply
        const formattedResults = searchResponse.results
          .map((result, index) => {
            const parts = [
              `**Result ${index + 1}${result.score ? ` (Score: ${result.score.toFixed(3)})` : ""}:**`
            ];

            // Extract content from various possible fields
            const content = result.content || result.text || result.payload?.content || result.payload?.text || JSON.stringify(result, null, 2);
            parts.push(content);

            return parts.join("\n");
          })
          .join("\n\n---\n\n");

        const summaryText = [
          `**Collection:** ${AIRWEAVE_COLLECTION}`,
          `**Results:** ${searchResponse.results.length}`,
          "",
          formattedResults || "No results found.",
        ].join("\n");

        return {
          content: [
            {
              type: "text",
              text: summaryText,
            },
          ],
        };
      }
    } catch (error) {
      console.error("Error in Airweave API request:", error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      return {
        content: [
          {
            type: "text",
            text: `**Error:** Failed to search collection.\n\n**Details:** ${errorMessage}\n\n**Debugging Info:**\n- Collection: ${AIRWEAVE_COLLECTION}\n- Base URL: ${AIRWEAVE_BASE_URL}\n- Endpoint: /collections/${AIRWEAVE_COLLECTION}/search`,
          },
        ],
      };
    }
  }
);

// Register a tool to get server configuration info
server.tool(
  "get-config",
  "Get the current Airweave MCP server configuration",
  {},
  async () => {
    return {
      content: [
        {
          type: "text",
          text: [
            "**Airweave MCP Server Configuration:**",
            "",
            `- **Collection ID:** ${AIRWEAVE_COLLECTION}`,
            `- **Base URL:** ${AIRWEAVE_BASE_URL}`,
            `- **API Key:** ${AIRWEAVE_API_KEY ? "✓ Configured" : "✗ Missing"}`,
            "",
            "**Available Commands:**",
            `- \`${toolName}\`: Search within the configured Airweave collection`,
            "- `get-config`: Show this configuration information",
          ].join("\n"),
        },
      ],
    };
  }
);

// Main function to start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr so it doesn't interfere with MCP protocol
  console.error("Airweave MCP Search Server started");
  console.error(`Collection: ${AIRWEAVE_COLLECTION}`);
  console.error(`Base URL: ${AIRWEAVE_BASE_URL}`);
}

// Handle graceful shutdown
process.on("SIGINT", () => {
  console.error("Shutting down Airweave MCP server...");
  process.exit(0);
});

process.on("SIGTERM", () => {
  console.error("Shutting down Airweave MCP server...");
  process.exit(0);
});

// Start the server
main().catch((error) => {
  console.error("Fatal error in Airweave MCP server:", error);
  process.exit(1);
});
