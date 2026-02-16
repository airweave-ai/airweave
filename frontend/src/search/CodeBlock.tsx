import React, { useState, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { apiClient, API_CONFIG } from '@/lib/api';
import { Terminal } from 'lucide-react';
import { useTheme } from '@/lib/theme-provider';
import { cn } from '@/lib/utils';
import { PythonIcon } from '@/components/icons/PythonIcon';
import { NodeIcon } from '@/components/icons/NodeIcon';
import { McpIcon } from '@/components/icons/McpIcon';

import { CodeBlock } from '@/components/ui/code-block';
import { DESIGN_SYSTEM } from '@/lib/design-system';

interface SearchConfig {
    search_method: "hybrid" | "neural" | "keyword";
    expansion_strategy: "auto" | "llm" | "no_expansion";
    enable_query_interpretation: boolean;
    recency_bias: number;
    enable_reranking: boolean;
    response_type: "raw" | "completion";
    filter?: any;
}

interface AgenticConfig {
    mode: "fast" | "thinking";
    filter: any[];  // backend-ready filter groups
}

interface ApiIntegrationDocProps {
    collectionReadableId: string;
    query?: string;
    searchConfig?: SearchConfig;
    agenticConfig?: AgenticConfig;
    filter?: string | null;
    apiKey?: string;
}

export const ApiIntegrationDoc = ({ collectionReadableId, query, searchConfig, agenticConfig, filter, apiKey = "YOUR_API_KEY" }: ApiIntegrationDocProps) => {
    // LiveApiDoc state
    const [apiTab, setApiTab] = useState<"rest" | "python" | "node" | "mcp">("rest");

    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';

    const isAgentic = !!agenticConfig;

    // ─── Agentic search snippets ─────────────────────────────────────
    const agenticEndpoints = useMemo(() => {
        if (!agenticConfig) return null;

        const apiBaseUrl = API_CONFIG.baseURL;
        const apiUrl = `${apiBaseUrl}/collections/${collectionReadableId}/agentic-search`;
        const searchQuery = query || "Ask a question about your data";

        const escapeForJson = (str: string) => str.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
        const escapeForPython = (str: string) => str.replace(/\\/g, '\\\\').replace(/"/g, '\\"');

        // Build request body
        const requestBody: any = {
            query: searchQuery,
            ...(agenticConfig.filter.length > 0 ? { filter: agenticConfig.filter } : {}),
            mode: agenticConfig.mode,
        };

        const jsonBody = JSON.stringify(requestBody, null, 2)
            .split('\n')
            .map((line, index, array) => {
                if (index === 0) return line;
                if (index === array.length - 1) return '  ' + line;
                return '  ' + line;
            })
            .join('\n');

        // cURL
        const curlSnippet = `# Agentic search
curl -X 'POST' \\
  '${apiUrl}' \\
  -H 'accept: application/json' \\
  -H 'x-api-key: ${apiKey}' \\
  -H 'Content-Type: application/json' \\
  -d '${jsonBody}'`;

        // Python
        const filterLines = agenticConfig.filter.length > 0
            ? `\n        filter=${JSON.stringify(agenticConfig.filter, null, 4)
                .split('\n')
                .map((l, i) => i === 0 ? l : '        ' + l)
                .join('\n')},`
            : '';

        const pythonSnippet =
            `from airweave import AirweaveSDK

client = AirweaveSDK(
    api_key="${apiKey}",
)

# Agentic search
response = client.collections.agentic_search(
    readable_id="${collectionReadableId}",
    request={
        "query": "${escapeForPython(searchQuery)}",${filterLines}
        "mode": "${agenticConfig.mode}",
    },
)
print(response.results, response.answer)`;

        // Node.js
        const nodeFilterLines = agenticConfig.filter.length > 0
            ? `\n            filter: ${JSON.stringify(agenticConfig.filter, null, 4)
                .split('\n')
                .map((l, i) => i === 0 ? l : '            ' + l)
                .join('\n')},`
            : '';

        const nodeSnippet =
            `import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "${apiKey}" });

// Agentic search
const response = await client.collections.agenticSearch(
    "${collectionReadableId}",
    {
        request: {
            query: "${escapeForJson(searchQuery)}",${nodeFilterLines}
            mode: "${agenticConfig.mode}",
        }
    }
);

console.log(response.results, response.answer);`;

        const configSnippet = `{
  "mcpServers": {
    "airweave-${collectionReadableId}": {
      "command": "npx",
      "args": ["airweave-mcp-search"],
      "env": {
        "AIRWEAVE_API_KEY": "${apiKey}",
        "AIRWEAVE_COLLECTION": "${collectionReadableId}",
        "AIRWEAVE_BASE_URL": "${API_CONFIG.baseURL}"
      }
    }
  }
}`;

        return { curlSnippet, pythonSnippet, nodeSnippet, configSnippet };
    }, [collectionReadableId, apiKey, agenticConfig, query]);

    // ─── Regular search snippets ─────────────────────────────────────
    const apiEndpoints = useMemo(() => {
        if (isAgentic) return null;

        const apiBaseUrl = API_CONFIG.baseURL;
        const apiUrl = `${apiBaseUrl}/collections/${collectionReadableId}/search`;
        const searchQuery = query || "Ask a question about your data";

        // Escape query for different contexts
        const escapeForJson = (str: string) => str.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
        const escapeForPython = (str: string) => str.replace(/\\/g, '\\\\').replace(/"/g, '\\"');

        // Parse filter if provided
        let parsedFilter = null;
        if (filter) {
            try {
                parsedFilter = JSON.parse(filter);
            } catch {
                parsedFilter = null;
            }
        }

        // Build request body with ALL parameters in specific order (new schema)
        const requestBody: any = {
            query: searchQuery,  // Will be escaped when stringified
            retrieval_strategy: searchConfig?.search_method || "hybrid",
            expand_query: searchConfig?.expansion_strategy !== "no_expansion",
            ...(parsedFilter ? { filter: parsedFilter } : {}),  // Include filter only if valid
            interpret_filters: searchConfig?.enable_query_interpretation || false,
            temporal_relevance: searchConfig?.recency_bias ?? 0.3,
            rerank: searchConfig?.enable_reranking ?? true,
            generate_answer: searchConfig?.response_type === "completion",
            limit: 20,
            offset: 0
        };

        // Create the cURL command with formatted JSON
        const jsonBody = JSON.stringify(requestBody, null, 2)
            .split('\n')
            .map((line, index, array) => {
                if (index === 0) return line;
                if (index === array.length - 1) return '  ' + line;
                return '  ' + line;
            })
            .join('\n');

        // Add note about query interpretation if enabled
        const interpretNote = searchConfig?.enable_query_interpretation
            ? `# Note: interpret_filters is enabled, which may automatically add\n# additional filters extracted from your natural language query.\n# The filter shown below is your manual filter only.\n\n`
            : '';

        const curlSnippet = `${interpretNote}curl -X 'POST' \\
  '${apiUrl}' \\
  -H 'accept: application/json' \\
  -H 'x-api-key: ${apiKey}' \\
  -H 'Content-Type: application/json' \\
  -d '${jsonBody}'`;

        // Create the Python code with ALL parameters in specific order
        const pythonFilterStr = parsedFilter ?
            JSON.stringify(parsedFilter, null, 4)
                .split('\n')
                .map((line, index) => index === 0 ? line : '        ' + line)
                .join('\n') :
            null;

        const pythonRequestParams = [
            `        query="${escapeForPython(searchQuery)}"`,
            `        retrieval_strategy=RetrievalStrategy.${(searchConfig?.search_method || "hybrid").toUpperCase()}`,
            `        expand_query=${searchConfig?.expansion_strategy !== "no_expansion" ? "True" : "False"}`,
            ...(pythonFilterStr ? [`        filter=${pythonFilterStr}`] : []),
            `        interpret_filters=${searchConfig?.enable_query_interpretation ? "True" : "False"}`,
            `        temporal_relevance=${searchConfig?.recency_bias ?? 0}`,
            `        rerank=${(searchConfig?.enable_reranking ?? true) ? "True" : "False"}`,
            `        generate_answer=${searchConfig?.response_type === "compilation" ? "True" : "False"}`,
            `        limit=1000`,
            `        offset=0`
        ];

        const pythonInterpretNote = searchConfig?.enable_query_interpretation
            ? `# Note: interpret_filters is enabled, which may automatically add
# additional filters extracted from your natural language query.
# The filter shown below is your manual filter only.

`
            : '';

        const pythonSnippet =
            `${pythonInterpretNote}from airweave import AirweaveSDK, SearchRequest, RetrievalStrategy

client = AirweaveSDK(
    api_key="${apiKey}",
)

result = client.collections.search(
    readable_id="${collectionReadableId}",
    request=SearchRequest(
${pythonRequestParams.join(',\n')}
    ),
)

print(result.completion)  # AI-generated answer (if generate_answer=True)
print(len(result.results))  # Number of results`;

        // Create the Node.js code with ALL parameters in specific order
        const nodeFilterStr = parsedFilter ?
            JSON.stringify(parsedFilter, null, 4)
                .split('\n')
                .map((line, index) => index === 0 ? line : '            ' + line)
                .join('\n') :
            null;

        const nodeRequestParams = [
            `            query: "${escapeForJson(searchQuery)}"`,
            `            retrievalStrategy: "${searchConfig?.search_method || "hybrid"}"`,
            `            expandQuery: ${searchConfig?.expansion_strategy !== "no_expansion"}`,
            ...(nodeFilterStr ? [`            filter: ${nodeFilterStr}`] : []),
            `            interpretFilters: ${searchConfig?.enable_query_interpretation || false}`,
            `            temporalRelevance: ${searchConfig?.recency_bias ?? 0}`,
            `            rerank: ${searchConfig?.enable_reranking ?? true}`,
            `            generateAnswer: ${searchConfig?.response_type === "completion"}`,
            `            limit: 1000`,
            `            offset: 0`
        ];

        const nodeInterpretNote = searchConfig?.enable_query_interpretation
            ? `// Note: interpretFilters is enabled, which may automatically add
// additional filters extracted from your natural language query.
// The filter shown below is your manual filter only.

`
            : '';

        const nodeSnippet =
            `${nodeInterpretNote}import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "${apiKey}" });

const result = await client.collections.search("${collectionReadableId}", {
    request: {
${nodeRequestParams.join(',\n')}
    }
});

console.log(result.completion);  // AI-generated answer (if generateAnswer=true)
console.log(result.results.length);  // Number of results`;

        // MCP Server code examples
        const configSnippet =
            `{
  "mcpServers": {
    "airweave-${collectionReadableId}": {
      "command": "npx",
      "args": ["airweave-mcp-search"],
      "env": {
        "AIRWEAVE_API_KEY": "${apiKey}",
        "AIRWEAVE_COLLECTION": "${collectionReadableId}",
        "AIRWEAVE_BASE_URL": "${API_CONFIG.baseURL}"
      }
    }
  }
}`;

        return {
            curlSnippet,
            pythonSnippet,
            nodeSnippet,
            configSnippet
        };
    }, [collectionReadableId, apiKey, searchConfig, query, filter, isAgentic]);

    // Resolved endpoints — whichever mode is active
    const endpoints = isAgentic ? agenticEndpoints : apiEndpoints;



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
                            {endpoints && apiTab === "rest" && (
                                <CodeBlock
                                    code={endpoints.curlSnippet}
                                    language="bash"
                                    badgeText="POST"
                                    badgeColor="bg-amber-600 hover:bg-amber-600"
                                    title={isAgentic
                                        ? `/collections/${collectionReadableId}/agentic-search`
                                        : `/collections/${collectionReadableId}/search`
                                    }
                                    footerContent={docLinkFooter}
                                    height="100%"
                                    className="h-full rounded-none border-none"
                                />
                            )}

                            {endpoints && apiTab === "python" && (
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

                            {endpoints && apiTab === "node" && (
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

                            {endpoints && apiTab === "mcp" && (
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
