// Configuration tool implementation

export function createConfigTool(searchToolNames: string[], collection: string, baseUrl: string, apiKey: string) {
    return {
        name: "get-config",
        description: "Get the current Airweave MCP server configuration",
        schema: {}, // Empty schema for no parameters
        handler: async () => {
            const searchToolsList = searchToolNames.length > 0
                ? searchToolNames.map(name => `- \`${name}\`: Search within the corresponding Airweave collection`).join("\n")
                : "- No search tools available";

            return {
                content: [
                    {
                        type: "text" as const,
                        text: [
                            "**Airweave MCP Server Configuration:**",
                            "",
                            `- **Fallback Collection ID:** ${collection}`,
                            `- **Base URL:** ${baseUrl}`,
                            `- **API Key:** ${apiKey ? "✓ Configured" : "✗ Missing"}`,
                            "",
                            "**Available Search Commands:**",
                            searchToolsList,
                            "",
                            "**Other Commands:**",
                            "- `get-config`: Show this configuration information",
                        ].join("\n"),
                    },
                ],
            };
        }
    };
}
