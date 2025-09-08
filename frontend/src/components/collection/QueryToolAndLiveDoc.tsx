import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { apiClient, API_CONFIG } from '@/lib/api';
import { Copy, Check, Braces, SearchCode, TerminalSquare, Clock, AlertCircle, ChevronDown, ChevronRight, Terminal, Code, Layers, Book } from 'lucide-react';
import { useTheme } from '@/lib/theme-provider';
import { cn } from '@/lib/utils';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PythonIcon } from '@/components/icons/PythonIcon';
import { NodeIcon } from '@/components/icons/NodeIcon';
import { McpIcon } from '@/components/icons/McpIcon';
import { ClaudeIcon } from '@/components/icons/ClaudeIcon';
import { CursorIcon } from '@/components/icons/CursorIcon';
import { WindsurfIcon } from '@/components/icons/WindsurfIcon';
import { CodeBlock } from '@/components/ui/code-block';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { JsonViewer } from '@textea/json-viewer';
import { ActionCheckResponse } from '@/types';

interface QueryToolAndLiveDocProps {
    collectionReadableId: string;
}

// Define response type enum to match backend
type ResponseType = 'raw' | 'completion';

export const QueryToolAndLiveDoc = ({ collectionReadableId }: QueryToolAndLiveDocProps) => {
    // QueryTool state
    const [query, setQuery] = useState('');
    const [responseType, setResponseType] = useState<ResponseType>('raw');
    const [completion, setCompletion] = useState('');
    const [objects, setObjects] = useState('');
    const [objectsData, setObjectsData] = useState<any>(null);  // Add state for parsed JSON
    const [isLoading, setIsLoading] = useState(false);
    const [statusCode, setStatusCode] = useState<number | null>(null);
    const [responseTime, setResponseTime] = useState<number | null>(null);
    const [searchStatus, setSearchStatus] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    // Usage limit state
    const [queriesAllowed, setQueriesAllowed] = useState(true);
    const [queryCheckDetails, setQueryCheckDetails] = useState<ActionCheckResponse | null>(null);
    const [isCheckingUsage, setIsCheckingUsage] = useState(true);

    // LiveApiDoc state
    const [viewMode, setViewMode] = useState<"restapi" | "mcpserver">("restapi");
    const [apiTab, setApiTab] = useState<"rest" | "python" | "node" | "claude" | "cursor" | "windsurf" | "server">("rest");
    const [apiKey, setApiKey] = useState<string>("YOUR_API_KEY");
    const [isLoadingApiKey, setIsLoadingApiKey] = useState(true);

    const { resolvedTheme } = useTheme();
    const responseRef = useRef<HTMLDivElement>(null);
    const isDark = resolvedTheme === 'dark';

    // Memoize expensive style objects
    const syntaxStyle = useMemo(() => isDark ? materialOceanic : oneLight, [isDark]);

    const customSyntaxStyle = useMemo(() => ({
        ...syntaxStyle,
        'pre[class*="language-"]': {
            ...syntaxStyle['pre[class*="language-"]'],
            background: 'transparent',
            margin: 0,
            padding: 0,
        },
        'code[class*="language-"]': {
            ...syntaxStyle['code[class*="language-"]'],
            background: 'transparent',
        }
    }), [syntaxStyle]);

    // Fetch API key
    useEffect(() => {
        const fetchApiKey = async () => {
            setIsLoadingApiKey(true);
            try {
                const response = await apiClient.get("/api-keys");
                if (response.ok) {
                    const data = await response.json();
                    // Get the first API key if available
                    if (Array.isArray(data) && data.length > 0 && data[0].decrypted_key) {
                        setApiKey(data[0].decrypted_key);
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

    // Memoize API URL to prevent unnecessary recalculations
    const apiUrl = useMemo(() => {
        const baseUrlDomain = API_CONFIG.baseURL.replace(/^https?:\/\//, '');
        const baseUrl = `${baseUrlDomain}/collections/${collectionReadableId || '{collection_id}'}/search`;
        const params = [];
        const exampleQuery = query || "Ask a question about your data";

        if (exampleQuery) {
            params.push(`query=${exampleQuery}`);
        }
        params.push(`response_type=${responseType}`);

        return `${baseUrl}?${params.join('&')}`;
    }, [collectionReadableId, query, responseType]);

    // Memoize API endpoints to prevent expensive recalculation on every render
    const apiEndpoints = useMemo(() => {
        const apiBaseUrl = API_CONFIG.baseURL;
        const apiUrl = `${apiBaseUrl}/collections/${collectionReadableId}/search`;
        const exampleQuery = query || "Ask a question about your data";

        // Create the cURL command
        const curlSnippet = `curl -X 'GET' \\
  '${apiUrl}?query=${encodeURIComponent(exampleQuery)}&response_type=${responseType}' \\
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
    query="${exampleQuery}",
    response_type="${responseType}"
)`;

        // Create the Node.js code
        const nodeSnippet =
            `import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "${apiKey}" });
await client.collections.searchCollection("${collectionReadableId}", {
    query: "${exampleQuery}",
    responseType: "${responseType}"
});`;

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

        const installSnippet =
            `# Install the MCP server globally
npm install -g airweave-mcp-search@1.0.7

# Or run directly with npx
npx airweave-mcp-search`;

        const cliSnippet =
            `# Set environment variables
export AIRWEAVE_API_KEY="${apiKey}"
export AIRWEAVE_COLLECTION="${collectionReadableId}"
export AIRWEAVE_BASE_URL="${API_CONFIG.baseURL}"

# Run the MCP server
airweave-mcp-search`;

        return {
            curlSnippet,
            pythonSnippet,
            nodeSnippet,
            configSnippet,
            installSnippet,
            cliSnippet
        };
    }, [collectionReadableId, query, responseType, apiKey]);

    // Reset tab when switching view modes to avoid invalid states
    const handleViewModeChange = useCallback((mode: "restapi" | "mcpserver") => {
        setViewMode(mode);
        if (mode === "restapi") {
            setApiTab("rest");
        } else {
            setApiTab("claude");
        }
    }, []);

    // Check if queries are allowed
    const checkQueryAction = useCallback(async () => {
        try {
            const response = await apiClient.get('/usage/check-action?action=queries');
            if (response.ok) {
                const data: ActionCheckResponse = await response.json();
                setQueriesAllowed(data.allowed);
                setQueryCheckDetails(data);
            }
        } catch (error) {
            console.error('Failed to check query action:', error);
            // Default to allowed on error to not block users
            setQueriesAllowed(true);
        } finally {
            setIsCheckingUsage(false);
        }
    }, []);

    // Check on mount and when collection changes
    useEffect(() => {
        setIsCheckingUsage(true);
        checkQueryAction();
    }, [collectionReadableId, checkQueryAction]);

    const handleSubmit = useCallback(async (e: React.FormEvent) => {
        e.preventDefault();

        // Don't proceed if query is empty or queries not allowed
        if (!query.trim() || !queriesAllowed) return;

        setIsLoading(true);
        setStatusCode(null);
        setResponseTime(null);
        setSearchStatus(null);
        const startTime = performance.now();

        try {
            // Use the collections search endpoint with response_type parameter
            const response = await apiClient.get(
                `/collections/${collectionReadableId}/search?query=${encodeURIComponent(query)}&response_type=${responseType}`
            );
            const endTime = performance.now();
            setResponseTime(Math.round(endTime - startTime));
            setStatusCode(response.status);

            if (!response.ok) {
                throw new Error(`Search failed: ${response.statusText}`);
            }

            const data = await response.json();

            // Update state based on the response format
            setSearchStatus(data.status || null);
            setObjects(JSON.stringify(data.results || [], null, 2));
            setObjectsData(data.results || []);  // Store parsed data

            if (responseType === 'completion') {
                setCompletion(data.completion || '');
            } else {
                setCompletion('');
            }

            // After successful query, re-check if queries are still allowed
            // This updates the UI immediately if user hits their limit
            await checkQueryAction();
        } catch (error) {
            console.error('Error searching:', error);
            setCompletion(`Error: ${error instanceof Error ? error.message : String(error)}`);
            setObjects('');
            setObjectsData(null);  // Clear parsed data
        } finally {
            setIsLoading(false);
        }
    }, [query, collectionReadableId, responseType, queriesAllowed, checkQueryAction]);

    const handleCopyObjects = useCallback(async () => {
        try {
            await navigator.clipboard.writeText(objects);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (error) {
            console.error('Failed to copy:', error);
        }
    }, [objects]);

    const handleCopyCompletion = useCallback(async () => {
        try {
            await navigator.clipboard.writeText(completion);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (error) {
            console.error('Failed to copy:', error);
        }
    }, [completion]);

    // Get status indicator colors - memoized
    const getStatusIndicator = useCallback((status: string | null) => {
        if (!status) return "bg-gray-400";

        switch (status) {
            case 'success':
                return isDark ? "bg-green-400" : "bg-green-500";
            case 'no_relevant_results':
                return isDark ? "bg-amber-400" : "bg-amber-500";
            default:
                return isDark ? "bg-red-400" : "bg-red-500";
        }
    }, [isDark]);

    // Memoize footer components
    const docLinkFooter = useMemo(() => (
        <div className="text-xs flex items-center gap-2">
            <span className={isDark ? "text-gray-400" : "text-gray-500"}>→</span>
            <a
                href="https://docs.airweave.ai/api-reference/collections/search-collection-advanced-collections-readable-id-search-post?explorer=true"
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
                Add this to your MCP client configuration file (usually{" "}
                {apiTab === "claude" && "~/.config/Claude/claude_desktop_config.json for Claude"}
                {apiTab === "cursor" && "~/.cursor/mcp.json for Cursor"}
                {apiTab === "windsurf" && "~/.windsurf/mcp.json for Windsurf"}
            </span>
        </div>
    ), [isDark, apiTab]);

    const mcpInstallFooter = useMemo(() => (
        <div className="text-xs flex items-center gap-2">
            <span className={isDark ? "text-gray-400" : "text-gray-500"}>→</span>
            <span className={isDark ? "text-gray-400" : "text-gray-500"}>
                After installation, configure your MCP client with the environment variables shown above
            </span>
        </div>
    ), [isDark]);

    return (
        <div className="w-full mb-6">
            {/* QUERY TOOL SECTION */}
            <div className="mb-8">
                {/* Header with collection name */}
                <div className="flex justify-between items-center mb-4">
                    <div className="flex items-center gap-3">
                        <h2 className="text-xl font-medium text-foreground">
                            Query your collection
                            <a
                                href="https://docs.airweave.ai/search"
                                target="_blank"
                                rel="noopener noreferrer"
                                className={cn(
                                    "inline-flex items-center gap-1 ml-2 text-xs align-super transition-all",
                                    isDark
                                        ? "text-blue-400 hover:text-blue-300"
                                        : "text-blue-600 hover:text-blue-700"
                                )}
                            >
                                <Book className="h-3 w-3" />
                                Read docs
                            </a>
                        </h2>
                    </div>
                </div>

                {/* API Endpoint display */}
                <div className="mb-5">
                    <div className="flex h-8 items-stretch rounded-md border overflow-hidden shadow-xs">
                        <div className={cn(
                            "flex items-center justify-center min-w-[48px]",
                            isDark ? "bg-emerald-900/40 text-emerald-300" : "bg-emerald-50 text-emerald-500"
                        )}>
                            <span className="text-xs font-semibold">GET</span>
                        </div>
                        <div className={cn(
                            "flex-grow flex items-center px-3 py-1.5 text-xs font-mono",
                            isDark
                                ? "bg-gray-900 text-gray-300"
                                : "bg-gray-50/80 text-gray-700"
                        )}>
                            <span className="opacity-75">{apiUrl}</span>
                        </div>
                        <div className="border-l flex items-center">
                            <Button
                                variant="ghost"
                                size="icon"
                                className={cn(
                                    "h-8 w-8 rounded-none",
                                    isDark ? "text-gray-400 hover:text-gray-300" : "text-gray-500 hover:text-gray-700"
                                )}
                                onClick={() => navigator.clipboard.writeText(`https://${apiUrl}`)}
                            >
                                <Copy className="h-3.5 w-3.5" />
                            </Button>
                        </div>
                    </div>
                </div>

                {/* Query input */}
                <div className="mb-5">
                    <TooltipProvider delayDuration={100}>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <form onSubmit={handleSubmit} className="flex items-stretch">
                                    {/* Query input field */}
                                    <div className={cn(
                                        "flex flex-1 h-9 rounded-l-md border-y border-l overflow-hidden",
                                        !queriesAllowed && "opacity-60"
                                    )}>
                                        <div className={cn(
                                            "flex items-center justify-center min-w-[70px] border-r",
                                            isDark
                                                ? "bg-gray-800/80 text-gray-300 border-gray-700"
                                                : "bg-gray-50/80 text-gray-600 border-gray-200"
                                        )}>
                                            <span className="text-xs font-medium">query=</span>
                                        </div>
                                        <input
                                            type="text"
                                            placeholder={queriesAllowed ? "Ask a question about your data" : "Query limit reached"}
                                            value={query}
                                            onChange={(e) => setQuery(e.target.value)}
                                            disabled={!queriesAllowed || isCheckingUsage}
                                            className={cn(
                                                "w-full px-3 h-full text-sm",
                                                isDark
                                                    ? "bg-gray-900 text-gray-200"
                                                    : "bg-white/90",
                                                !queriesAllowed && "cursor-not-allowed"
                                            )}
                                            style={{ outline: 'none', border: 'none' }}
                                        />
                                    </div>

                                    {/* Response type selector */}
                                    <div className={cn(
                                        "h-9 border-y border-l border-r-0",
                                        isDark ? "border-gray-700" : "border-gray-200",
                                        !queriesAllowed && "opacity-60"
                                    )}>
                                        <Select
                                            value={responseType}
                                            onValueChange={(value) => setResponseType(value as ResponseType)}
                                            disabled={!queriesAllowed || isCheckingUsage}
                                        >
                                            <SelectTrigger
                                                className={cn(
                                                    "h-full border-0 rounded-none min-w-[120px] text-xs font-mono focus:outline-none focus:ring-0 focus:ring-offset-0",
                                                    isDark ? "bg-gray-800" : "bg-gray-50",
                                                    !queriesAllowed && "cursor-not-allowed"
                                                )}
                                            >
                                                <span>{responseType}</span>
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="raw" className="text-xs font-mono">raw</SelectItem>
                                                <SelectItem value="completion" className="text-xs font-mono">completion</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    {/* Search button */}
                                    <Button
                                        type="submit"
                                        disabled={isLoading || !query.trim() || !queriesAllowed || isCheckingUsage}
                                        className={cn(
                                            "rounded-l-none rounded-r-md h-9 px-5",
                                            isDark
                                                ? queriesAllowed && query.trim() ? "bg-blue-600 hover:bg-blue-700" : "bg-gray-600 hover:bg-gray-600 cursor-not-allowed"
                                                : queriesAllowed && query.trim() ? "bg-blue-500 hover:bg-blue-600" : "bg-gray-400 hover:bg-gray-400 cursor-not-allowed"
                                        )}
                                    >
                                        {isLoading ? 'Searching...' : isCheckingUsage ? 'Checking...' : 'Search'}
                                    </Button>
                                </form>
                            </TooltipTrigger>
                            {!queriesAllowed && queryCheckDetails?.reason === 'usage_limit_exceeded' && (
                                <TooltipContent className="max-w-xs">
                                    <p className="text-xs">
                                        Query limit reached.{' '}
                                        <a
                                            href="/organization/settings?tab=billing"
                                            className="underline"
                                            onClick={(e) => e.stopPropagation()}
                                        >
                                            Upgrade your plan
                                        </a>
                                        {' '}for more queries.
                                    </p>
                                </TooltipContent>
                            )}
                        </Tooltip>
                    </TooltipProvider>
                </div>

                {/* Unified Response Section */}
                <div ref={responseRef} className={cn(
                    "mt-8 rounded-lg shadow-sm overflow-hidden",
                    (!completion && !objects && !isLoading) ? "hidden" : "",
                    isDark ? "bg-gray-950" : "bg-white",
                    isDark ? "ring-1 ring-gray-800" : "ring-1 ring-gray-200"
                )}>
                    {/* Status Ribbon - Always visible */}
                    {isLoading ? (
                        <div className="h-1.5 w-full relative overflow-hidden">
                            <div className={cn(
                                "absolute inset-0 h-1.5 bg-gradient-to-r from-blue-500 to-indigo-500"
                            )}></div>
                            <div className={cn(
                                "absolute inset-0 h-1.5 bg-gradient-to-r from-transparent via-white to-transparent",
                                "animate-shimmer"
                            )}
                                style={{
                                    backgroundSize: '200% 100%',
                                    animationDuration: '1.5s',
                                    animationIterationCount: 'infinite',
                                    animationTimingFunction: 'linear'
                                }}
                            ></div>
                        </div>
                    ) : (
                        <div className={cn(
                            "h-1.5 w-full bg-gradient-to-r",
                            searchStatus === 'success'
                                ? "from-green-500 to-emerald-500"
                                : searchStatus === 'no_relevant_results'
                                    ? "from-amber-400 to-amber-500"
                                    : "from-gray-400 to-gray-500"
                        )}></div>
                    )}

                    {/* Simplified Metadata Bar */}
                    <div className={cn(
                        "w-full py-2 px-3",
                        isDark ? "bg-gray-900/60" : "bg-gray-50/80",
                        "flex items-center justify-between"
                    )}>
                        <div className="flex items-center gap-3">
                            <div className="flex items-center">
                                <Layers className="h-3.5 w-3.5 mr-2 opacity-70" />
                                <span className="text-xs font-medium">Response Metadata</span>
                            </div>

                            {searchStatus && (
                                <div className="flex items-center">
                                    <div className={cn(
                                        "h-1.5 w-1.5 rounded-full mr-1.5",
                                        getStatusIndicator(searchStatus)
                                    )}></div>
                                    <span className="text-xs opacity-80">
                                        {searchStatus.replace(/_/g, ' ')}
                                    </span>
                                </div>
                            )}
                        </div>

                        <div className="flex items-center gap-3">
                            {statusCode && (
                                <div className="flex items-center text-xs opacity-80">
                                    <TerminalSquare className="h-3.5 w-3.5 mr-1.5" />
                                    <span className="font-mono">HTTP {statusCode}</span>
                                </div>
                            )}

                            {responseTime && (
                                <div className="flex items-center text-xs opacity-80">
                                    <Clock className="h-3.5 w-3.5 mr-1.5" />
                                    <span className="font-mono">{responseTime}ms</span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Content Section */}
                    <div className="flex flex-col">
                        {/* Completion Section */}
                        {responseType === 'completion' && (completion || isLoading) ? (
                            <div className={cn(
                                "border-t",
                                isDark ? "border-gray-800/50" : "border-gray-200/50"
                            )}>
                                <div className={cn(
                                    "flex items-center justify-between p-3 border-b bg-gradient-to-r",
                                    isDark
                                        ? "from-indigo-950/30 to-indigo-900/20 border-indigo-900/30 text-indigo-300"
                                        : "from-indigo-50 to-indigo-100/50 border-indigo-100/80 text-indigo-700"
                                )}>
                                    <div className="flex items-center">
                                        <SearchCode className="h-3.5 w-3.5 mr-2" />
                                        <span className="text-xs font-semibold">Completion</span>
                                    </div>
                                    {!isLoading && completion && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className={cn(
                                                "text-xs gap-1 h-6",
                                                isDark ? "text-indigo-300 hover:text-indigo-200" : "text-indigo-600 hover:text-indigo-700"
                                            )}
                                            onClick={handleCopyCompletion}
                                        >
                                            <Copy className="h-3 w-3" />
                                            Copy
                                        </Button>
                                    )}
                                </div>

                                <div className={cn(
                                    "p-4 prose max-w-none overflow-auto max-h-[438px]",
                                    isDark
                                        ? "prose-invert bg-gradient-to-b from-gray-900/70 to-gray-900/50 text-gray-200"
                                        : "bg-gradient-to-b from-white to-gray-50/80 prose-gray text-gray-800"
                                )}
                                    style={{ fontSize: '0.875rem' }}>
                                    {isLoading ? (
                                        <div className="animate-pulse h-32 w-full">
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-5/6 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-2/3 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
                                        </div>
                                    ) : (
                                        <ReactMarkdown
                                            remarkPlugins={[remarkGfm]}
                                            components={{
                                                h1: ({ node, ...props }) => <h1 style={{ fontSize: '2em', fontWeight: 'bold', margin: '0.67em 0' }} {...props} />,
                                                h2: ({ node, ...props }) => <h2 style={{ fontSize: '1.5em', fontWeight: 'bold', margin: '0.83em 0' }} {...props} />,
                                                h3: ({ node, ...props }) => <h3 style={{ fontSize: '1.17em', fontWeight: 'bold', margin: '1em 0' }} {...props} />,
                                                ul: ({ node, ...props }) => <ul style={{ listStyle: 'disc', paddingLeft: '2em', margin: '1em 0' }} {...props} />,
                                                li: ({ node, ...props }) => <li style={{ display: 'list-item', margin: '0.5em 0' }} {...props} />,
                                                code(props) {
                                                    const { children, className, node, ...rest } = props;
                                                    const match = /language-(\w+)/.exec(className || '');
                                                    return match ? (
                                                        <SyntaxHighlighter
                                                            language={match[1]}
                                                            style={syntaxStyle}
                                                            customStyle={{
                                                                margin: 0,
                                                                borderRadius: '0.75rem',
                                                                background: isDark ? 'rgba(17, 24, 39, 0.8)' : 'rgba(249, 250, 251, 0.8)'
                                                            }}
                                                        >
                                                            {String(children).replace(/\n$/, '')}
                                                        </SyntaxHighlighter>
                                                    ) : (
                                                        <code {...rest} className={cn(className, "bg-opacity-75 px-1.5 py-0.5 rounded text-sm")}>
                                                            {children}
                                                        </code>
                                                    );
                                                }
                                            }}
                                        >
                                            {completion}
                                        </ReactMarkdown>
                                    )}
                                </div>
                            </div>
                        ) : null}

                        {/* JSON Response Section */}
                        {(objects || isLoading) ? (
                            <div className={cn(
                                "border-t",
                                isDark ? "border-gray-800/50" : "border-gray-200/50"
                            )}>
                                <div className={cn(
                                    "flex items-center justify-between p-3 border-b bg-gradient-to-r",
                                    isDark
                                        ? "from-gray-800/90 to-gray-900/70 border-gray-700/50 text-gray-300"
                                        : "from-gray-50 to-gray-100/70 border-gray-200/70 text-gray-700"
                                )}>
                                    <div className="flex items-center">
                                        <Braces className="h-3.5 w-3.5 mr-2 opacity-80" />
                                        <span className="text-xs font-semibold">JSON RESPONSE</span>
                                    </div>
                                    {!isLoading && objects && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-xs gap-1 h-6"
                                            onClick={handleCopyObjects}
                                        >
                                            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                                            Copy
                                        </Button>
                                    )}
                                </div>
                                <div className={cn(
                                    "overflow-auto max-h-[438px] bg-gradient-to-b",
                                    isDark ? "from-gray-900/80 to-gray-900/60" : "from-white to-gray-50/80"
                                )}>
                                    {isLoading ? (
                                        <div className="p-4 animate-pulse space-y-2">
                                            <div className="flex gap-2">
                                                <div className="h-4 w-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                                <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                            </div>
                                            <div className="flex gap-2 ml-4">
                                                <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                                <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                            </div>
                                            <div className="flex gap-2 ml-4">
                                                <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                                <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                            </div>
                                            <div className="flex gap-2 ml-4">
                                                <div className="h-4 w-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                                <div className="h-4 w-36 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                            </div>
                                            <div className="h-4 w-8 bg-gray-200 dark:bg-gray-700 rounded"></div>
                                        </div>
                                    ) : (
                                        <div className="p-4">
                                            <JsonViewer
                                                value={objectsData}
                                                theme={isDark ? "dark" : "light"}
                                                style={{
                                                    fontSize: '0.8rem',
                                                    fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace',
                                                }}
                                                rootName={false}
                                                displayDataTypes={false}
                                                enableClipboard={false}
                                                quotesOnKeys={false}
                                                indentWidth={2}
                                                collapseStringsAfterLength={100}
                                                groupArraysAfterLength={100}
                                                defaultInspectDepth={4}
                                                defaultInspectControl={(path, value) => {
                                                    if (path[path.length - 1] === 'payload') {
                                                        return true;
                                                    }
                                                    if (path.length <= 2) {
                                                        return true;
                                                    }
                                                    return undefined;
                                                }}
                                            />
                                        </div>
                                    )}
                                </div>
                            </div>
                        ) : null}
                    </div>
                </div>
            </div>

            {/* LIVE API DOC SECTION */}
            <div className="mb-8 mt-12">
                {/* Header with title */}
                <div className="flex justify-between items-center mb-4">
                    <div className="flex items-center gap-3">
                        <h2 className="text-xl font-medium text-foreground opacity-90">Integrate with the endpoint</h2>
                    </div>
                </div>

                <div className="flex w-full flex-col md:flex-row gap-4 opacity-95">
                    {/* Left section with view mode buttons */}
                    <div className="w-full md:w-1/4 flex flex-row md:flex-col gap-3">
                        <Button
                            variant="outline"
                            onClick={() => handleViewModeChange("restapi")}
                            className={cn(
                                "w-full justify-start p-4 rounded-md text-sm flex items-center gap-3 transition-all",
                                "border-input bg-background text-muted-foreground hover:text-foreground hover:bg-accent/10 dark:border-border dark:bg-card dark:hover:bg-muted",
                                viewMode === "restapi" && "border-primary bg-primary/5 dark:bg-primary/10 text-primary dark:text-primary-foreground font-medium"
                            )}
                        >
                            <Code className={cn(
                                "h-5 w-5",
                                viewMode === "restapi" ? "text-primary" : "text-muted-foreground"
                            )} />
                            <span>RestAPI</span>
                        </Button>

                        {/* MCP Server button - now enabled */}
                        <Button
                            variant="outline"
                            onClick={() => handleViewModeChange("mcpserver")}
                            className={cn(
                                "w-full justify-start p-4 rounded-md text-sm flex items-center gap-3 transition-all",
                                "border-input bg-background text-muted-foreground hover:text-foreground hover:bg-accent/10 dark:border-border dark:bg-card dark:hover:bg-muted",
                                viewMode === "mcpserver" && "border-primary bg-primary/5 dark:bg-primary/10 text-primary dark:text-primary-foreground font-medium"
                            )}
                        >
                            <McpIcon className={cn(
                                "h-5 w-5",
                                viewMode === "mcpserver" ? "text-primary" : "text-muted-foreground"
                            )} />
                            <span>MCP Server</span>
                        </Button>
                    </div>

                    {/* Right content area */}
                    <div className="w-full md:w-3/4">
                        <div className={cn(
                            "rounded-lg overflow-hidden border",
                            isDark ? "bg-gray-900 border-gray-800" : "bg-gray-100 border-gray-200"
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
                                                    : "text-gray-700 hover:bg-gray-200/80",
                                                apiTab === "rest"
                                                    ? isDark ? "bg-gray-800" : "bg-gray-200"
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
                                                    : "text-gray-700 hover:bg-gray-200/80",
                                                apiTab === "python"
                                                    ? isDark ? "bg-gray-800" : "bg-gray-200"
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
                                                    : "text-gray-700 hover:bg-gray-200/80",
                                                apiTab === "node"
                                                    ? isDark ? "bg-gray-800" : "bg-gray-200"
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
                                                    : "text-gray-700 hover:bg-gray-200/80",
                                                apiTab === "claude"
                                                    ? isDark ? "bg-gray-800" : "bg-gray-200"
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
                                                    : "text-gray-700 hover:bg-gray-200/80",
                                                apiTab === "cursor"
                                                    ? isDark ? "bg-gray-800" : "bg-gray-200"
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
                                                    : "text-gray-700 hover:bg-gray-200/80",
                                                apiTab === "windsurf"
                                                    ? isDark ? "bg-gray-800" : "bg-gray-200"
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
                                                    : "text-gray-700 hover:bg-gray-200/80",
                                                apiTab === "server"
                                                    ? isDark ? "bg-gray-800" : "bg-gray-200"
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
                            <div className="h-[330px]">
                                {viewMode === "restapi" && (
                                    <>
                                        {apiTab === "rest" && (
                                            <CodeBlock
                                                code={apiEndpoints.curlSnippet}
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
                                                code={apiEndpoints.pythonSnippet}
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
                                                code={apiEndpoints.nodeSnippet}
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
                                                code={apiEndpoints.configSnippet}
                                                language="json"
                                                badgeText="CONFIG"
                                                badgeColor="bg-purple-600 hover:bg-purple-600"
                                                title="Claude Desktop MCP Configuration"
                                                footerContent={mcpConfigFooter}
                                                height="100%"
                                                className="h-full rounded-none border-none"
                                            />
                                        )}

                                        {apiTab === "cursor" && (
                                            <CodeBlock
                                                code={apiEndpoints.configSnippet}
                                                language="json"
                                                badgeText="CONFIG"
                                                badgeColor="bg-blue-600 hover:bg-blue-600"
                                                title="Cursor MCP Configuration"
                                                footerContent={mcpConfigFooter}
                                                height="100%"
                                                className="h-full rounded-none border-none"
                                            />
                                        )}

                                        {apiTab === "windsurf" && (
                                            <CodeBlock
                                                code={apiEndpoints.configSnippet}
                                                language="json"
                                                badgeText="CONFIG"
                                                badgeColor="bg-teal-600 hover:bg-teal-600"
                                                title="Windsurf MCP Configuration"
                                                footerContent={mcpConfigFooter}
                                                height="100%"
                                                className="h-full rounded-none border-none"
                                            />
                                        )}

                                        {apiTab === "server" && (
                                            <CodeBlock
                                                code={apiEndpoints.installSnippet}
                                                language="bash"
                                                badgeText="INSTALL"
                                                badgeColor="bg-gray-600 hover:bg-gray-600"
                                                title="Install MCP Server"
                                                footerContent={mcpInstallFooter}
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
        </div>
    );
};
