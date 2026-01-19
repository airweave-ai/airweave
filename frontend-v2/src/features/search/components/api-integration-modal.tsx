import { Code, Terminal } from "lucide-react";
import { type ReactNode, useCallback, useMemo, useState } from "react";

import {
  ClaudeIcon,
  CursorIcon,
  McpIcon,
  NodeIcon,
  PythonIcon,
  WindsurfIcon,
} from "@/components/icons/tech-icons";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { API_BASE_URL } from "@/lib/api";
import { cn } from "@/lib/utils";

import type { SearchConfig } from "../types";

interface ApiIntegrationModalProps {
  collectionReadableId: string;
  query?: string;
  searchConfig?: SearchConfig;
  filter?: string | null;
  apiKey?: string;
}

type ViewMode = "restapi" | "mcpserver";
type RestApiTab = "rest" | "python" | "node";
type McpTab = "claude" | "cursor" | "windsurf" | "server";
type ApiTab = RestApiTab | McpTab;

interface TabConfig {
  id: ApiTab;
  label: string;
  icon: ReactNode;
}

interface HeaderInfo {
  badge: string;
  badgeColor: string;
  title: string;
}

const REST_TABS: TabConfig[] = [
  { id: "rest", label: "cURL", icon: <Terminal className="size-4" /> },
  { id: "python", label: "Python", icon: <PythonIcon className="size-4" /> },
  { id: "node", label: "Node.js", icon: <NodeIcon className="size-4" /> },
];

const MCP_TABS: TabConfig[] = [
  { id: "claude", label: "Claude", icon: <ClaudeIcon className="size-5" /> },
  { id: "cursor", label: "Cursor", icon: <CursorIcon className="size-5" /> },
  {
    id: "windsurf",
    label: "Windsurf",
    icon: <WindsurfIcon className="size-5" />,
  },
  { id: "server", label: "Server/Other", icon: <McpIcon className="size-4" /> },
];

const MCP_CONFIG_PATHS: Record<McpTab, string> = {
  claude: "~/.config/Claude/claude_desktop_config.json",
  cursor: "~/.cursor/mcp.json",
  windsurf: "~/.windsurf/mcp.json",
  server: "",
};

const LANGUAGE_BY_TAB: Record<ApiTab, string> = {
  rest: "bash",
  python: "python",
  node: "typescript",
  claude: "json",
  cursor: "json",
  windsurf: "json",
  server: "bash",
};

export function ApiIntegrationModal({
  collectionReadableId,
  query,
  searchConfig,
  filter,
  apiKey = "YOUR_API_KEY",
}: ApiIntegrationModalProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("restapi");
  const [activeTab, setActiveTab] = useState<ApiTab>("rest");

  const handleViewModeChange = useCallback((mode: ViewMode) => {
    setViewMode(mode);
    setActiveTab(mode === "restapi" ? "rest" : "claude");
  }, []);

  const snippets = useMemo(() => {
    const apiUrl = `${API_BASE_URL}/collections/${collectionReadableId}/search`;
    const searchQuery = query || "Ask a question about your data";

    const escapeString = (str: string) =>
      str.replace(/\\/g, "\\\\").replace(/"/g, '\\"');

    let parsedFilter = null;
    if (filter) {
      try {
        parsedFilter = JSON.parse(filter);
      } catch {
        parsedFilter = null;
      }
    }

    const requestBody: Record<string, unknown> = {
      query: searchQuery,
      retrieval_strategy: searchConfig?.search_method || "hybrid",
      expand_query: searchConfig?.expansion_strategy !== "no_expansion",
      ...(parsedFilter ? { filter: parsedFilter } : {}),
      interpret_filters: searchConfig?.enable_query_interpretation || false,
      temporal_relevance: searchConfig?.recency_bias ?? 0.3,
      rerank: searchConfig?.enable_reranking ?? true,
      generate_answer: searchConfig?.response_type === "completion",
      limit: 20,
      offset: 0,
    };

    const jsonBody = JSON.stringify(requestBody, null, 2)
      .split("\n")
      .map((line, index, array) => {
        if (index === 0) return line;
        if (index === array.length - 1) return "  " + line;
        return "  " + line;
      })
      .join("\n");

    const interpretNote = searchConfig?.enable_query_interpretation
      ? `# Note: interpret_filters is enabled, which may automatically add\n# additional filters extracted from your natural language query.\n# The filter shown below is your manual filter only.\n\n`
      : "";

    const curlSnippet = `${interpretNote}curl -X 'POST' \\
  '${apiUrl}' \\
  -H 'accept: application/json' \\
  -H 'x-api-key: ${apiKey}' \\
  -H 'Content-Type: application/json' \\
  -d '${jsonBody}'`;

    const pythonFilterStr = parsedFilter
      ? JSON.stringify(parsedFilter, null, 4)
          .split("\n")
          .map((line, index) => (index === 0 ? line : "        " + line))
          .join("\n")
      : null;

    const pythonRequestParams = [
      `        query="${escapeString(searchQuery)}"`,
      `        retrieval_strategy=RetrievalStrategy.${(searchConfig?.search_method || "hybrid").toUpperCase()}`,
      `        expand_query=${searchConfig?.expansion_strategy !== "no_expansion" ? "True" : "False"}`,
      ...(pythonFilterStr ? [`        filter=${pythonFilterStr}`] : []),
      `        interpret_filters=${searchConfig?.enable_query_interpretation ? "True" : "False"}`,
      `        temporal_relevance=${searchConfig?.recency_bias ?? 0}`,
      `        rerank=${(searchConfig?.enable_reranking ?? true) ? "True" : "False"}`,
      `        generate_answer=${searchConfig?.response_type === "completion" ? "True" : "False"}`,
      `        limit=1000`,
      `        offset=0`,
    ];

    const pythonInterpretNote = searchConfig?.enable_query_interpretation
      ? `# Note: interpret_filters is enabled, which may automatically add
# additional filters extracted from your natural language query.
# The filter shown below is your manual filter only.

`
      : "";

    const pythonSnippet = `${pythonInterpretNote}from airweave import AirweaveSDK, SearchRequest, RetrievalStrategy

client = AirweaveSDK(
    api_key="${apiKey}",
)

result = client.collections.search(
    readable_id="${collectionReadableId}",
    request=SearchRequest(
${pythonRequestParams.join(",\n")}
    ),
)

print(result.completion)  # AI-generated answer (if generate_answer=True)
print(len(result.results))  # Number of results`;

    const nodeFilterStr = parsedFilter
      ? JSON.stringify(parsedFilter, null, 4)
          .split("\n")
          .map((line, index) => (index === 0 ? line : "            " + line))
          .join("\n")
      : null;

    const nodeRequestParams = [
      `            query: "${escapeString(searchQuery)}"`,
      `            retrievalStrategy: "${searchConfig?.search_method || "hybrid"}"`,
      `            expandQuery: ${searchConfig?.expansion_strategy !== "no_expansion"}`,
      ...(nodeFilterStr ? [`            filter: ${nodeFilterStr}`] : []),
      `            interpretFilters: ${searchConfig?.enable_query_interpretation || false}`,
      `            temporalRelevance: ${searchConfig?.recency_bias ?? 0}`,
      `            rerank: ${searchConfig?.enable_reranking ?? true}`,
      `            generateAnswer: ${searchConfig?.response_type === "completion"}`,
      `            limit: 1000`,
      `            offset: 0`,
    ];

    const nodeInterpretNote = searchConfig?.enable_query_interpretation
      ? `// Note: interpretFilters is enabled, which may automatically add
// additional filters extracted from your natural language query.
// The filter shown below is your manual filter only.

`
      : "";

    const nodeSnippet = `${nodeInterpretNote}import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "${apiKey}" });

const result = await client.collections.search("${collectionReadableId}", {
    request: {
${nodeRequestParams.join(",\n")}
    }
});

console.log(result.completion);  // AI-generated answer (if generateAnswer=true)
console.log(result.results.length);  // Number of results`;

    const mcpConfigSnippet = `{
  "mcpServers": {
    "airweave-${collectionReadableId}": {
      "command": "npx",
      "args": ["airweave-mcp-search"],
      "env": {
        "AIRWEAVE_API_KEY": "${apiKey}",
        "AIRWEAVE_COLLECTION": "${collectionReadableId}",
        "AIRWEAVE_BASE_URL": "${API_BASE_URL}"
      }
    }
  }
}`;

    const mcpInstallSnippet = `# Install the MCP server globally
npm install -g airweave-mcp-search@1.0.7

# Or run directly with npx
npx airweave-mcp-search`;

    return {
      curl: curlSnippet,
      python: pythonSnippet,
      node: nodeSnippet,
      mcpConfig: mcpConfigSnippet,
      mcpInstall: mcpInstallSnippet,
    };
  }, [collectionReadableId, apiKey, searchConfig, query, filter]);

  const codeByTab: Record<ApiTab, string> = useMemo(
    () => ({
      rest: snippets.curl,
      python: snippets.python,
      node: snippets.node,
      claude: snippets.mcpConfig,
      cursor: snippets.mcpConfig,
      windsurf: snippets.mcpConfig,
      server: snippets.mcpInstall,
    }),
    [snippets]
  );

  const headerByTab: Record<ApiTab, HeaderInfo> = useMemo(
    () => ({
      rest: {
        badge: "POST",
        badgeColor: "bg-amber-600",
        title: `/collections/${collectionReadableId}/search`,
      },
      python: { badge: "SDK", badgeColor: "bg-blue-600", title: "AirweaveSDK" },
      node: {
        badge: "SDK",
        badgeColor: "bg-blue-600",
        title: "AirweaveSDKClient",
      },
      claude: {
        badge: "CONFIG",
        badgeColor: "bg-purple-600",
        title: "Claude Desktop MCP Configuration",
      },
      cursor: {
        badge: "CONFIG",
        badgeColor: "bg-blue-600",
        title: "Cursor MCP Configuration",
      },
      windsurf: {
        badge: "CONFIG",
        badgeColor: "bg-teal-600",
        title: "Windsurf MCP Configuration",
      },
      server: {
        badge: "INSTALL",
        badgeColor: "bg-slate-600",
        title: "Install MCP Server",
      },
    }),
    [collectionReadableId]
  );

  const renderFooter = () => {
    if (viewMode === "mcpserver") {
      if (activeTab === "server") {
        return (
          <span className="text-slate-400">
            → After installation, configure your MCP client with the environment
            variables shown above
          </span>
        );
      }
      return (
        <span className="text-slate-400">
          → Add this to your MCP client configuration file (
          {MCP_CONFIG_PATHS[activeTab as McpTab]})
        </span>
      );
    }
    return (
      <span>
        →{" "}
        <a
          href="https://docs.airweave.ai/api-reference/collections/search-advanced-collections-readable-id-search-post"
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 hover:underline"
        >
          Explore the full API documentation
        </a>
      </span>
    );
  };

  const headerInfo = headerByTab[activeTab];
  const tabs = viewMode === "restapi" ? REST_TABS : MCP_TABS;

  return (
    <div className="mb-6 w-full">
      <div className="flex gap-4">
        {/* Left section with view mode buttons */}
        <div className="flex w-36 shrink-0 flex-col gap-2">
          <Button
            variant="outline"
            onClick={() => handleViewModeChange("restapi")}
            className={cn(
              "flex w-full items-center justify-start gap-2 border-slate-700 bg-slate-900 p-3 text-sm",
              viewMode === "restapi"
                ? "border-primary bg-primary/10 text-primary"
                : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            )}
          >
            <Code className="size-4" />
            <span>REST API</span>
          </Button>
          <Button
            variant="outline"
            onClick={() => handleViewModeChange("mcpserver")}
            className={cn(
              "flex w-full items-center justify-start gap-2 border-slate-700 bg-slate-900 p-3 text-sm",
              viewMode === "mcpserver"
                ? "border-primary bg-primary/10 text-primary"
                : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            )}
          >
            <McpIcon className="size-4" />
            <span>MCP Server</span>
          </Button>
        </div>

        {/* Right content area */}
        <div className="flex-1 overflow-hidden rounded-lg border border-slate-700 bg-slate-900">
          {/* Tabs */}
          <div className="flex w-fit space-x-1 overflow-x-auto border-b border-slate-700 p-2">
            {tabs.map((tab) => (
              <Button
                key={tab.id}
                variant="ghost"
                size="sm"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 rounded-md",
                  activeTab === tab.id
                    ? "bg-slate-800 text-slate-200"
                    : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
                )}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </Button>
            ))}
          </div>

          {/* Code content */}
          <CodeBlock
            code={codeByTab[activeTab]}
            language={LANGUAGE_BY_TAB[activeTab]}
            badgeText={headerInfo.badge}
            badgeColor={headerInfo.badgeColor}
            title={headerInfo.title}
            footerContent={<span className="text-xs">{renderFooter()}</span>}
            height={400}
            className="rounded-none border-0"
          />
        </div>
      </div>
    </div>
  );
}
