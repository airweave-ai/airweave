import React, { useState, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { API_CONFIG } from '@/lib/api';
import { Terminal } from 'lucide-react';
import { useTheme } from '@/lib/theme-provider';
import { cn } from '@/lib/utils';
import { PythonIcon } from '@/components/icons/PythonIcon';
import { NodeIcon } from '@/components/icons/NodeIcon';
import { McpIcon } from '@/components/icons/McpIcon';

import { CodeBlock } from '@/components/ui/code-block';
import { DESIGN_SYSTEM } from '@/lib/design-system';

// Local type aliases — avoids circular import with SearchBox
type SearchTier = "instant" | "classic" | "agentic";
type RetrievalStrategy = "hybrid" | "neural" | "keyword";

interface ApiIntegrationDocProps {
    collectionReadableId: string;
    query?: string;
    tier: SearchTier;
    retrievalStrategy?: RetrievalStrategy;
    thinking?: boolean;
    filter?: any[];
    apiKey?: string;
}

export const ApiIntegrationDoc = ({
    collectionReadableId,
    query,
    tier,
    retrievalStrategy = "hybrid",
    thinking = false,
    filter = [],
    apiKey = "YOUR_API_KEY",
}: ApiIntegrationDocProps) => {
    const [apiTab, setApiTab] = useState<"rest" | "python" | "node" | "mcp">("rest");

    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';

    const endpoints = useMemo(() => {
        const apiBaseUrl = API_CONFIG.baseURL;
        const searchQuery = query || "Ask a question about your data";
        const hasFilters = filter.length > 0;

        const escapeForJson = (str: string) => str.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
        const escapeForPython = (str: string) => str.replace(/\\/g, '\\\\').replace(/"/g, '\\"');

        // v2 endpoint URL
        const apiUrl = `${apiBaseUrl}/collections/${collectionReadableId}/search/${tier}`;

        // Request body per tier
        let requestBody: any;
        switch (tier) {
            case "instant":
                requestBody = {
                    query: searchQuery,
                    retrieval_strategy: retrievalStrategy,
                    ...(hasFilters && { filter }),
                };
                break;
            case "classic":
                requestBody = {
                    query: searchQuery,
                    ...(hasFilters && { filter }),
                };
                break;
            case "agentic":
                requestBody = {
                    query: searchQuery,
                    thinking,
                    ...(hasFilters && { filter }),
                };
                break;
        }

        const jsonBody = JSON.stringify(requestBody, null, 2)
            .split('\n')
            .map((line, index, array) => {
                if (index === 0) return line;
                if (index === array.length - 1) return '  ' + line;
                return '  ' + line;
            })
            .join('\n');

        // ─── cURL ────────────────────────────────────────────────────────
        const curlSnippet = `curl -X 'POST' \\
  '${apiUrl}' \\
  -H 'accept: application/json' \\
  -H 'x-api-key: ${apiKey}' \\
  -H 'Content-Type: application/json' \\
  -d '${jsonBody}'`;

        // ─── Python ──────────────────────────────────────────────────────
        const sdkMethodPython = tier === "instant" ? "search_instant"
            : tier === "classic" ? "search_classic"
            : "search_agentic";

        const pythonParams: string[] = [
            `        "query": "${escapeForPython(searchQuery)}"`,
        ];
        if (tier === "instant") {
            pythonParams.push(`        "retrieval_strategy": "${retrievalStrategy}"`);
        }
        if (tier === "agentic") {
            pythonParams.push(`        "thinking": ${thinking ? "True" : "False"}`);
        }
        if (hasFilters) {
            pythonParams.push(`        "filter": ${JSON.stringify(filter, null, 4)
                .split('\n')
                .map((l, i) => i === 0 ? l : '        ' + l)
                .join('\n')}`);
        }

        const pythonSnippet =
            `from airweave import AirweaveSDK

client = AirweaveSDK(
    api_key="${apiKey}",
)

response = client.collections.${sdkMethodPython}(
    readable_id="${collectionReadableId}",
    request={
${pythonParams.join(',\n')},
    },
)
print(response.results${tier === "agentic" ? ", response.answer" : ""})`;

        // ─── Node.js ─────────────────────────────────────────────────────
        const sdkMethodNode = tier === "instant" ? "searchInstant"
            : tier === "classic" ? "searchClassic"
            : "searchAgentic";

        const nodeParams: string[] = [
            `            query: "${escapeForJson(searchQuery)}"`,
        ];
        if (tier === "instant") {
            nodeParams.push(`            retrievalStrategy: "${retrievalStrategy}"`);
        }
        if (tier === "agentic") {
            nodeParams.push(`            thinking: ${thinking}`);
        }
        if (hasFilters) {
            nodeParams.push(`            filter: ${JSON.stringify(filter, null, 4)
                .split('\n')
                .map((l, i) => i === 0 ? l : '            ' + l)
                .join('\n')}`);
        }

        const nodeSnippet =
            `import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "${apiKey}" });

const response = await client.collections.${sdkMethodNode}(
    "${collectionReadableId}",
    {
        request: {
${nodeParams.join(',\n')},
        }
    }
);

console.log(response.results${tier === "agentic" ? ", response.answer" : ""});`;

        // ─── MCP config (collection-level, not tier-specific) ────────────
        const configSnippet = `{
  "mcpServers": {
    "airweave-${collectionReadableId}": {
      "command": "npx",
      "args": ["airweave-mcp-search"],
      "env": {
        "AIRWEAVE_API_KEY": "${apiKey}",
        "AIRWEAVE_COLLECTION": "${collectionReadableId}",
        "AIRWEAVE_BASE_URL": "${apiBaseUrl}"
      }
    }
  }
}`;

        return { curlSnippet, pythonSnippet, nodeSnippet, configSnippet };
    }, [collectionReadableId, apiKey, tier, retrievalStrategy, thinking, filter, query]);

    // Memoize footer components
    const docLinkFooter = useMemo(() => (
        <div className="text-xs flex items-center gap-2">
            <span className={isDark ? "text-gray-400" : "text-gray-500"}>→</span>
            <a
                href="https://docs.airweave.ai/api-reference/collections/search-advanced-collections-readable-id-search-post"
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
    ), [isDark]);

    const mcpConfigFooter = useMemo(() => (
        <div className="text-xs flex items-center gap-2">
            <span className={isDark ? "text-gray-400" : "text-gray-500"}>→</span>
            <span className={isDark ? "text-gray-400" : "text-gray-500"}>
                Add this to your MCP client configuration file (e.g., ~/.config/Claude/claude_desktop_config.json)
            </span>
        </div>
    ), [isDark]);

    return (
        <div className="w-full mb-6">
            {/* LIVE API DOC SECTION */}
            <div className="mb-8">
                <div className="w-full opacity-95">
                    <div className={cn(
                        DESIGN_SYSTEM.radius.card,
                        "overflow-hidden border",
                        isDark ? "bg-gray-900 border-gray-800" : "bg-gray-100 border-gray-200"
                    )}>
                        {/* Tabs */}
                        <div className="flex space-x-1 p-2 w-fit overflow-x-auto border-b border-b-gray-200 dark:border-b-gray-800">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setApiTab("rest")}
                                className={cn(
                                    DESIGN_SYSTEM.radius.button,
                                    DESIGN_SYSTEM.typography.sizes.header,
                                    "flex items-center",
                                    DESIGN_SYSTEM.spacing.gaps.standard,
                                    isDark
                                        ? "text-gray-200 hover:bg-gray-800/80"
                                        : "text-gray-700 hover:bg-gray-200/80",
                                    apiTab === "rest"
                                        ? isDark ? "bg-gray-800" : "bg-gray-200"
                                        : ""
                                )}
                            >
                                <Terminal className={DESIGN_SYSTEM.icons.large} />
                                <span>cURL</span>
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setApiTab("python")}
                                className={cn(
                                    DESIGN_SYSTEM.radius.button,
                                    DESIGN_SYSTEM.typography.sizes.header,
                                    "flex items-center",
                                    DESIGN_SYSTEM.spacing.gaps.standard,
                                    isDark
                                        ? "text-gray-200 hover:bg-gray-800/80"
                                        : "text-gray-700 hover:bg-gray-200/80",
                                    apiTab === "python"
                                        ? isDark ? "bg-gray-800" : "bg-gray-200"
                                        : ""
                                )}
                            >
                                <PythonIcon className={DESIGN_SYSTEM.icons.large} />
                                <span>Python</span>
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setApiTab("node")}
                                className={cn(
                                    DESIGN_SYSTEM.radius.button,
                                    DESIGN_SYSTEM.typography.sizes.header,
                                    "flex items-center",
                                    DESIGN_SYSTEM.spacing.gaps.standard,
                                    isDark
                                        ? "text-gray-200 hover:bg-gray-800/80"
                                        : "text-gray-700 hover:bg-gray-200/80",
                                    apiTab === "node"
                                        ? isDark ? "bg-gray-800" : "bg-gray-200"
                                        : ""
                                )}
                            >
                                <NodeIcon className={DESIGN_SYSTEM.icons.large} />
                                <span>Node.js</span>
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setApiTab("mcp")}
                                className={cn(
                                    DESIGN_SYSTEM.radius.button,
                                    DESIGN_SYSTEM.typography.sizes.header,
                                    "flex items-center",
                                    DESIGN_SYSTEM.spacing.gaps.standard,
                                    isDark
                                        ? "text-gray-200 hover:bg-gray-800/80"
                                        : "text-gray-700 hover:bg-gray-200/80",
                                    apiTab === "mcp"
                                        ? isDark ? "bg-gray-800" : "bg-gray-200"
                                        : ""
                                )}
                            >
                                <McpIcon className={DESIGN_SYSTEM.icons.large} />
                                <span>MCP</span>
                            </Button>
                        </div>

                        {/* Tab Content */}
                        <div className={"h-[460px]"}>
                            {apiTab === "rest" && (
                                <CodeBlock
                                    code={endpoints.curlSnippet}
                                    language="bash"
                                    badgeText="POST"
                                    badgeColor="bg-amber-600 hover:bg-amber-600"
                                    title={`/collections/${collectionReadableId}/search/${tier}`}
                                    footerContent={docLinkFooter}
                                    height="100%"
                                    className="h-full rounded-none border-none"
                                />
                            )}

                            {apiTab === "python" && (
                                <CodeBlock
                                    code={endpoints.pythonSnippet}
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
                                    code={endpoints.nodeSnippet}
                                    language="javascript"
                                    badgeText="SDK"
                                    badgeColor="bg-blue-600 hover:bg-blue-600"
                                    title="AirweaveSDKClient"
                                    footerContent={docLinkFooter}
                                    height="100%"
                                    className="h-full rounded-none border-none"
                                />
                            )}

                            {apiTab === "mcp" && (
                                <CodeBlock
                                    code={endpoints.configSnippet}
                                    language="json"
                                    badgeText="CONFIG"
                                    badgeColor="bg-purple-600 hover:bg-purple-600"
                                    title="MCP Configuration"
                                    footerContent={mcpConfigFooter}
                                    height="100%"
                                    className="h-full rounded-none border-none"
                                />
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
