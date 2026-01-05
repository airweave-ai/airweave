/**
 * ApiIntegrationModal - Code snippets for API integration
 *
 * Generates ready-to-use code examples in cURL, Python, Node.js, and MCP formats
 * based on current search configuration.
 */

import { Check, Copy, Terminal } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { API_BASE_URL } from "@/lib/api";
import { cn } from "@/lib/utils";

import type { SearchConfig } from "../types";

// Icons for language tabs
function PythonIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M11.914 0C5.82 0 6.2 2.656 6.2 2.656l.007 2.752h5.814v.826H3.9S0 5.789 0 11.969c0 6.18 3.403 5.96 3.403 5.96h2.03v-2.867s-.109-3.42 3.35-3.42h5.766s3.24.052 3.24-3.148V3.202S18.28 0 11.914 0zM8.708 1.85c.578 0 1.048.473 1.048 1.053s-.47 1.052-1.048 1.052c-.579 0-1.048-.473-1.048-1.052 0-.58.47-1.053 1.048-1.053z" />
      <path d="M12.086 24c6.093 0 5.713-2.656 5.713-2.656l-.007-2.752h-5.814v-.826h8.121s3.9.445 3.9-5.735c0-6.18-3.402-5.96-3.402-5.96h-2.03v2.867s.109 3.42-3.35 3.42H9.45s-3.24-.052-3.24 3.148v5.292S5.72 24 12.086 24zm3.206-1.85c-.579 0-1.048-.473-1.048-1.053s.47-1.052 1.048-1.052c.578 0 1.048.473 1.048 1.052 0 .58-.47 1.053-1.048 1.053z" />
    </svg>
  );
}

function NodeIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M11.998 24c-.321 0-.641-.084-.922-.247l-2.936-1.737c-.438-.245-.224-.332-.08-.383.585-.203.703-.25 1.328-.604.066-.037.152-.023.22.017l2.256 1.339a.29.29 0 00.272 0l8.795-5.076a.277.277 0 00.134-.238V6.921a.282.282 0 00-.137-.242l-8.791-5.072a.278.278 0 00-.271 0L3.075 6.68a.281.281 0 00-.139.24v10.15c0 .099.053.19.137.239l2.409 1.392c1.307.654 2.108-.116 2.108-.89V7.787c0-.142.114-.253.256-.253h1.115c.139 0 .255.112.255.253v10.021c0 1.745-.95 2.745-2.604 2.745-.509 0-.909 0-2.026-.55l-2.304-1.326A1.85 1.85 0 011.36 17.07V6.921c0-.679.362-1.312.949-1.653l8.795-5.082a1.929 1.929 0 011.891 0l8.794 5.082a1.85 1.85 0 01.951 1.653v10.15a1.852 1.852 0 01-.951 1.652l-8.794 5.078c-.28.163-.599.247-.92.247" />
    </svg>
  );
}

function McpIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
    </svg>
  );
}

interface ApiIntegrationModalProps {
  collectionReadableId: string;
  query?: string;
  searchConfig?: SearchConfig;
  filter?: string | null;
  apiKey?: string;
}

type ApiTab = "rest" | "python" | "node" | "mcp";

export function ApiIntegrationModal({
  collectionReadableId,
  query,
  searchConfig,
  filter,
  apiKey = "YOUR_API_KEY",
}: ApiIntegrationModalProps) {
  const [activeTab, setActiveTab] = useState<ApiTab>("rest");
  const [copied, setCopied] = useState(false);

  // Generate code snippets based on current configuration
  const snippets = useMemo(() => {
    const apiUrl = `${API_BASE_URL}/collections/${collectionReadableId}/search`;
    const searchQuery = query || "Ask a question about your data";

    // Escape helpers
    const escapeForJson = (str: string) =>
      str.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
    const escapeForPython = (str: string) =>
      str.replace(/\\/g, "\\\\").replace(/"/g, '\\"');

    // Parse filter if provided
    let parsedFilter = null;
    if (filter) {
      try {
        parsedFilter = JSON.parse(filter);
      } catch {
        parsedFilter = null;
      }
    }

    // Build request body
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

    // cURL snippet
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

    // Python snippet
    const pythonFilterStr = parsedFilter
      ? JSON.stringify(parsedFilter, null, 4)
          .split("\n")
          .map((line, index) => (index === 0 ? line : "        " + line))
          .join("\n")
      : null;

    const pythonRequestParams = [
      `        query="${escapeForPython(searchQuery)}"`,
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

    // Node.js snippet
    const nodeFilterStr = parsedFilter
      ? JSON.stringify(parsedFilter, null, 4)
          .split("\n")
          .map((line, index) => (index === 0 ? line : "            " + line))
          .join("\n")
      : null;

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

    // MCP config snippet
    const mcpSnippet = `{
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

    return {
      curl: curlSnippet,
      python: pythonSnippet,
      node: nodeSnippet,
      mcp: mcpSnippet,
    };
  }, [collectionReadableId, apiKey, searchConfig, query, filter]);

  const handleCopy = async () => {
    const codeMap = {
      rest: snippets.curl,
      python: snippets.python,
      node: snippets.node,
      mcp: snippets.mcp,
    };
    await navigator.clipboard.writeText(codeMap[activeTab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="mb-6 w-full">
      <div className="overflow-hidden rounded-lg border border-slate-700 bg-slate-900">
        {/* Tabs */}
        <div className="flex w-fit space-x-1 overflow-x-auto border-b border-slate-700 p-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setActiveTab("rest")}
            className={cn(
              "flex items-center gap-2 rounded-md",
              activeTab === "rest"
                ? "bg-slate-800 text-slate-200"
                : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
            )}
          >
            <Terminal className="size-4" />
            <span>cURL</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setActiveTab("python")}
            className={cn(
              "flex items-center gap-2 rounded-md",
              activeTab === "python"
                ? "bg-slate-800 text-slate-200"
                : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
            )}
          >
            <PythonIcon className="size-4" />
            <span>Python</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setActiveTab("node")}
            className={cn(
              "flex items-center gap-2 rounded-md",
              activeTab === "node"
                ? "bg-slate-800 text-slate-200"
                : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
            )}
          >
            <NodeIcon className="size-4" />
            <span>Node.js</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setActiveTab("mcp")}
            className={cn(
              "flex items-center gap-2 rounded-md",
              activeTab === "mcp"
                ? "bg-slate-800 text-slate-200"
                : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
            )}
          >
            <McpIcon className="size-4" />
            <span>MCP</span>
          </Button>
        </div>

        {/* Code content */}
        <div className="relative h-[460px]">
          {/* Header with badge and copy */}
          <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-xs text-white",
                  activeTab === "rest" && "bg-amber-600",
                  activeTab === "python" && "bg-blue-600",
                  activeTab === "node" && "bg-blue-600",
                  activeTab === "mcp" && "bg-purple-600"
                )}
              >
                {activeTab === "rest" && "POST"}
                {activeTab === "python" && "SDK"}
                {activeTab === "node" && "SDK"}
                {activeTab === "mcp" && "CONFIG"}
              </span>
              <span className="text-xs font-medium text-slate-300">
                {activeTab === "rest" &&
                  `/collections/${collectionReadableId}/search`}
                {activeTab === "python" && "AirweaveSDK"}
                {activeTab === "node" && "AirweaveSDKClient"}
                {activeTab === "mcp" && "MCP Configuration"}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="size-6 p-0 text-slate-400 hover:text-white"
              onClick={handleCopy}
            >
              {copied ? (
                <Check className="size-3" />
              ) : (
                <Copy className="size-3" />
              )}
            </Button>
          </div>

          {/* Code display */}
          <div className="h-[calc(100%-88px)] overflow-auto bg-black px-4 py-3">
            <pre className="font-mono text-xs text-slate-300">
              {activeTab === "rest" && snippets.curl}
              {activeTab === "python" && snippets.python}
              {activeTab === "node" && snippets.node}
              {activeTab === "mcp" && snippets.mcp}
            </pre>
          </div>

          {/* Footer */}
          <div className="border-t border-slate-800 px-4 py-2 text-xs text-slate-400">
            {activeTab === "mcp" ? (
              <span>
                → Add this to your MCP client configuration file (e.g.,
                ~/.config/Claude/claude_desktop_config.json)
              </span>
            ) : (
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
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
