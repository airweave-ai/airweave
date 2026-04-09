import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Terminal, Code } from 'lucide-react';
import { cn } from '@/lib/utils';
import { CodeBlock } from '@/components/ui/code-block';
import { PythonIcon } from '@/components/icons/PythonIcon';
import { NodeIcon } from '@/components/icons/NodeIcon';
import { McpIcon } from '@/components/icons/McpIcon';
import { ClaudeIcon } from '@/components/icons/ClaudeIcon';
import { CursorIcon } from '@/components/icons/CursorIcon';
import { WindsurfIcon } from '@/components/icons/WindsurfIcon';
import { useTheme } from '@/lib/theme-provider';
import { apiClient, API_CONFIG } from '@/lib/api';

interface LiveApiDocProps {
    collectionReadableId: string;
}

export const LiveApiDoc = ({ collectionReadableId }: LiveApiDocProps) => {
    // Set default view mode to restapi
    const [viewMode, setViewMode] = useState<"restapi" | "mcpserver">("restapi");
    // Updated to handle both RestAPI and MCP Server tabs
    const [apiTab, setApiTab] = useState<"rest" | "python" | "node" | "claude" | "cursor" | "windsurf" | "server">("rest");
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const lastUserMessage = "What are the key features of this product?";
    const [apiKey, setApiKey] = useState<string>("YOUR_API_KEY");
    const [isLoadingApiKey, setIsLoadingApiKey] = useState(true);

    // Fetch API key
    useEffect(() => {
        const fetchApiKey = async () => {
            setIsLoadingApiKey(true);
            try {
                const response = await apiClient.get("/api-keys");
                if (response.ok) {
                    const data = await response.json();
                    // Get the first API key if available
                    if (Array.isArray(data) && data.length > 0) {
                        const prefix = data[0].key_prefix || "????????";
                        setApiKey(`${prefix}...`);
                    }
                }
            } catch (err) {
                console.error("Error fetching API key:", err);
            } finally {
                setIsLoadingApiKey(false);
            }
        };

        fetchApiKey();
    }, []);

    // Reset tab when switching view modes to avoid invalid states
    const handleViewModeChange = (mode: "restapi" | "mcpserver") => {
        setViewMode(mode);
        if (mode === "restapi") {
            setApiTab("rest");
        } else {
            setApiTab("claude");
        }
    };

    // Function to build API URLs from settings
    const getApiEndpoints = () => {
        const apiBaseUrl = API_CONFIG.baseURL;
        const apiUrl = `${apiBaseUrl}/collections/${collectionReadableId}/search`;

        // Create the cURL command
        const curlSnippet = `curl -X 'GET' \\
  '${apiUrl}?query=${encodeURIComponent(lastUserMessage)}' \\
  -H 'accept: application/json' \\
  -H 'x-api-key: ${apiKey}' \\
  -H 'Content-Type: application/json'`;

        // Create the Python code
        const pythonSnippet =
            `from airweave import AirweaveSDK

client = AirweaveSDK(
    api_key="${apiKey}",
)
client.collections.search_collection(
    readable_id="${collectionReadableId}",
    query="${lastUserMessage}",
)`;

        // Create the Node.js code
        const nodeSnippet =
            `import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "${apiKey}" });
await client.collections.searchCollection("${collectionReadableId}", {
    query: "${lastUserMessage}"
});`;

        // MCP Server code examples
        const configSnippet =
            `  "mcpServers": {
    "airweave_${collectionReadableId.substring(0, 8)}": {
      "url": "${API_CONFIG.baseURL.replace(/^https?:\/\//, 'https://')}/airweave/server/${collectionReadableId}?agent=cursor"
    }
  }
`;


        const cliSnippet =
            `# MCP Server CLI
mcp-cli connect --server localhost:8000 --auth-token ${apiKey}
mcp-cli query search --collection-id ${collectionReadableId} --query "${lastUserMessage}"
`;

        return {
            curlSnippet,
            pythonSnippet,
            nodeSnippet,
            configSnippet,
            cliSnippet
        };
    };

    const docLinkFooter = (
        <div className="text-xs flex items-center gap-2">
            <span className={isDark ? "text-gray-400" : "text-gray-500"}>→</span>
            <a
                href="https://docs.airweave.ai/api-reference/collections/search-collection"
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                    "hover:underline transition-all",
                    isDark ? "text-blue-400 hover:text-blue-300" : "text-blue-600 hover:text-blue-700"
                )}
            >
                Explore the full API documentation
            </a>
        </div>
    );

    return (
        <div className="mb-8">
            {/* Header with title */}
            <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-3">
                    <h2 className="text-xl font-medium text-foreground opacity-90">Integrate with the endpoint</h2>
                </div>
            </div>

            <div className="flex w-full flex-col md:flex-row gap-4 opacity-95">
                {/* Left section with view mode buttons - REORDERED with RestAPI on top */}
                <div className="w-full md:w-1/4 flex flex-row md:flex-col gap-3">
                    <Button
                        variant="outline"
                        onClick={() => handleViewModeChange("restapi")}
                        className={cn(
                            "w-full justify-start p-4 rounded-md text-sm flex items-center gap-3 transition-all",
                            "border-input bg-background text-muted-foreground hover:text-foreground hover:bg-accent/10 dark:border-border dark:bg-card dark:hover:bg-muted",
                            viewMode === "restapi" && "border-primary bg-primary/5 dark:bg-primary/10 text-primary dark:text-primary-foreground font-medium shadow-sm"
                        )}
                    >
                        <Code className={cn(
                            "h-5 w-5",
                            viewMode === "restapi" ? "text-primary" : "text-muted-foreground"
                        )} />
                        <span>RestAPI</span>
                    </Button>

                    {/* MCP Server button - now disabled and faint */}
                    <Button
                        variant="outline"
                        disabled={true}
                        className={cn(
                            "w-full justify-start p-4 rounded-md text-sm flex items-center gap-3 relative",
                            "border-input bg-background opacity-50 cursor-not-allowed",
                            isDark ? "text-gray-500 border-gray-700" : "text-gray-400 border-gray-200"
                        )}
                    >
                        <McpIcon className="h-5 w-5 text-muted-foreground opacity-50" />
                        <span>MCP Server</span>
                        <span className={cn(
                            "absolute top-2 right-2 px-1.5 py-0- text-[9px] font-medium rounded-sm tracking-tight",
                            isDark ? "bg-gray-800 text-gray-400" : "bg-gray-50 text-gray-500"
                        )}>
                            Coming soon
                        </span>
                    </Button>
                </div>

                {/* Right content area */}
                <div className="w-full md:w-3/4">
                    <div className={cn(
                        "rounded-lg overflow-hidden border",
                        isDark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200 shadow-sm"
                    )}>
                        {/* Tabs - Different tabs based on view mode */}
                        <div className="flex space-x-1 p-2 w-fit overflow-x-auto border-b border-b-gray-200 dark:border-b-gray-800">
                            {viewMode === "restapi" ? (
                                <>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("rest")}
                                        className={cn(
                                            "rounded-md text-sm flex items-center gap-2",
                                            isDark
                                                ? "text-gray-200 hover:bg-gray-800/80"
                                                : "text-gray-700 hover:bg-gray-50",
                                            apiTab === "rest"
                                                ? isDark ? "bg-gray-800" : "bg-blue-50/50 text-blue-700"
                                                : ""
                                        )}
                                    >
                                        <Terminal className="h-5 w-5" />
                                        <span>cURL</span>
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("python")}
                                        className={cn(
                                            "rounded-md text-sm flex items-center gap-2",
                                            isDark
                                                ? "text-gray-200 hover:bg-gray-800/80"
                                                : "text-gray-700 hover:bg-gray-50",
                                            apiTab === "python"
                                                ? isDark ? "bg-gray-800" : "bg-blue-50/50 text-blue-700"
                                                : ""
                                        )}
                                    >
                                        <PythonIcon className="h-5 w-5" />
                                        <span>Python</span>
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("node")}
                                        className={cn(
                                            "rounded-md text-sm flex items-center gap-2",
                                            isDark
                                                ? "text-gray-200 hover:bg-gray-800/80"
                                                : "text-gray-700 hover:bg-gray-50",
                                            apiTab === "node"
                                                ? isDark ? "bg-gray-800" : "bg-blue-50/50 text-blue-700"
                                                : ""
                                        )}
                                    >
                                        <NodeIcon className="h-5 w-5" />
                                        <span>Node.js</span>
                                    </Button>
                                </>
                            ) : (
                                <>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("claude")}
                                        className={cn(
                                            "rounded-md text-sm flex items-center gap-2",
                                            isDark
                                                ? "text-gray-200 hover:bg-gray-800/80"
                                                : "text-gray-700 hover:bg-gray-50",
                                            apiTab === "claude"
                                                ? isDark ? "bg-gray-800" : "bg-blue-50/50 text-blue-700"
                                                : ""
                                        )}
                                    >
                                        <ClaudeIcon className="h-6 w-6" />
                                        <span>Claude</span>
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("cursor")}
                                        className={cn(
                                            "rounded-md text-sm flex items-center gap-2",
                                            isDark
                                                ? "text-gray-200 hover:bg-gray-800/80"
                                                : "text-gray-700 hover:bg-gray-50",
                                            apiTab === "cursor"
                                                ? isDark ? "bg-gray-800" : "bg-blue-50/50 text-blue-700"
                                                : ""
                                        )}
                                    >
                                        <CursorIcon className="h-6 w-6" />
                                        <span>Cursor</span>
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("windsurf")}
                                        className={cn(
                                            "rounded-md text-sm flex items-center gap-2",
                                            isDark
                                                ? "text-gray-200 hover:bg-gray-800/80"
                                                : "text-gray-700 hover:bg-gray-50",
                                            apiTab === "windsurf"
                                                ? isDark ? "bg-gray-800" : "bg-blue-50/50 text-blue-700"
                                                : ""
                                        )}
                                    >
                                        <WindsurfIcon className="h-6 w-6" />
                                        <span>Windsurf</span>
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setApiTab("server")}
                                        className={cn(
                                            "rounded-md text-sm flex items-center gap-2",
                                            isDark
                                                ? "text-gray-200 hover:bg-gray-800/80"
                                                : "text-gray-700 hover:bg-gray-50",
                                            apiTab === "server"
                                                ? isDark ? "bg-gray-800" : "bg-blue-50/50 text-blue-700"
                                                : ""
                                        )}
                                    >
                                        <McpIcon className="h-5 w-5" />
                                        <span>Server/Other</span>
                                    </Button>
                                </>
                            )}
                        </div>

                        {/* Tab Content */}
                        <div className="h-[250px]">
                            {viewMode === "restapi" && (
                                <>
                                    {apiTab === "rest" && (
                                        <CodeBlock
                                            code={getApiEndpoints().curlSnippet}
                                            language="bash"
                                            badgeText="GET"
                                            badgeColor="bg-emerald-600 hover:bg-emerald-600"
                                            title={`/collections/${collectionReadableId}/search`}
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full rounded-none border-none"
                                        />
                                    )}

                                    {apiTab === "python" && (
                                        <CodeBlock
                                            code={getApiEndpoints().pythonSnippet}
                                            language="python"
                                            badgeText="SDK"
                                            badgeColor="bg-blue-600 hover:bg-blue-600"
                                            title="AirweaveSDK"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full rounded-none border-none"
                                        />
                                    )}

                                    {apiTab === "node" && (
                                        <CodeBlock
                                            code={getApiEndpoints().nodeSnippet}
                                            language="javascript"
                                            badgeText="SDK"
                                            badgeColor="bg-blue-600 hover:bg-blue-600"
                                            title="AirweaveSDKClient"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full rounded-none border-none"
                                        />
                                    )}
                                </>
                            )}

                            {viewMode === "mcpserver" && (
                                <>
                                    {apiTab === "claude" && (
                                        <CodeBlock
                                            code={getApiEndpoints().configSnippet}
                                            language="yaml"
                                            badgeText="CONFIG"
                                            badgeColor="bg-purple-600 hover:bg-purple-600"
                                            title="MCP Server Configuration"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full rounded-none border-none"
                                        />
                                    )}

                                    {apiTab === "cursor" && (
                                        <CodeBlock
                                            code={getApiEndpoints().configSnippet}
                                            language="yaml"
                                            badgeText="CONFIG"
                                            badgeColor="bg-purple-600 hover:bg-purple-600"
                                            title="MCP Server Configuration"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full rounded-none border-none"
                                        />
                                    )}

                                    {apiTab === "windsurf" && (
                                        <CodeBlock
                                            code={getApiEndpoints().configSnippet}
                                            language="yaml"
                                            badgeText="CONFIG"
                                            badgeColor="bg-purple-600 hover:bg-purple-600"
                                            title="MCP Server Configuration"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full rounded-none border-none"
                                        />
                                    )}

                                    {apiTab === "server" && (
                                        <CodeBlock
                                            code={getApiEndpoints().cliSnippet}
                                            language="bash"
                                            badgeText="SERVER"
                                            badgeColor="bg-gray-600 hover:bg-gray-600"
                                            title="MCP Command Line"
                                            footerContent={docLinkFooter}
                                            height="100%"
                                            className="h-full rounded-none border-none"
                                        />
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
