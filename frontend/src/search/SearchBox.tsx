import { useEffect, useState, useCallback, useRef } from "react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import { Button } from "@/components/ui/button";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { ArrowUp, CodeXml, X, Loader2, Square, ListStart, ChartScatter, RefreshCw, Brain, Zap } from "lucide-react";
import { FiGitMerge, FiType, FiLayers, FiFilter, FiSliders, FiMessageSquare } from "react-icons/fi";
import { ApiIntegrationDoc } from "@/search/CodeBlock";
import { JsonFilterEditor } from "@/search/JsonFilterEditor";
import { FilterBuilderPopover, FilterGroup, toBackendFilterGroups, countActiveFilters } from "@/search/FilterBuilderModal";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { apiClient } from "@/lib/api";
import type { SearchEvent, PartialStreamUpdate, StreamPhase } from "@/search/types";
import { DESIGN_SYSTEM } from "@/lib/design-system";
import { SingleActionCheckResponse } from "@/types";

// Search method types
type SearchMethod = "hybrid" | "neural" | "keyword";

// Search mode: regular pipeline search vs agentic multi-step search
export type SearchMode = "search" | "agent";
type AgenticMode = "fast" | "thinking";

// Toggle state interface
interface SearchToggles {
    queryExpansion: boolean;
    filter: boolean;
    queryInterpretation: boolean;
    reRanking: boolean;
    answer: boolean;
}

// Search configuration interface
export interface SearchConfig {
    search_method: SearchMethod;
    expansion_strategy: "auto" | "no_expansion";
    enable_query_interpretation: boolean;
    recency_bias: number;  // Always 0 - feature under construction
    enable_reranking: boolean;
    response_type: "completion" | "raw";
    filter?: any;
}

// Component props
interface SearchBoxProps {
    collectionId: string;
    onSearch: (response: any, responseType: 'raw' | 'completion', responseTime: number) => void;
    onSearchStart?: (responseType: 'raw' | 'completion') => void;
    onSearchEnd?: () => void;
    className?: string;
    disabled?: boolean;  // Disable search when no sources are connected
    // Streaming callbacks (Milestone 3)
    onStreamEvent?: (event: SearchEvent) => void;
    onStreamUpdate?: (partial: PartialStreamUpdate) => void;
    onCancel?: () => void;
    // Search mode
    agenticEnabled?: boolean;
    searchMode?: SearchMode;
    onSearchModeChange?: (mode: SearchMode) => void;
}

class TransientStreamError extends Error {
    constructor(message?: string) {
        super(message);
        this.name = "TransientStreamError";
    }
}

/**
 * SearchBox Component
 *
 * A comprehensive search interface component that handles:
 * - Query input with textarea
 * - Search method selection (hybrid/neural/keyword)
 * - Various search options with tooltips
 * - Filter configuration with JSON editor
 * - Recency bias slider
 * - API integration code modal
 * - Search execution and response handling
 */
export const SearchBox: React.FC<SearchBoxProps> = ({
    collectionId,
    onSearch,
    onSearchStart,
    onSearchEnd,
    onStreamEvent: onStreamEventProp,
    onStreamUpdate: onStreamUpdateProp,
    onCancel,
    className,
    disabled = false,
    agenticEnabled = true,
    searchMode = "agent",
    onSearchModeChange,
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    // Core search state
    const [query, setQuery] = useState("");
    const [searchMethod, setSearchMethod] = useState<SearchMethod>("hybrid");
    const [isSearching, setIsSearching] = useState(false);

    // Agentic search sub-mode (fast/thinking)
    const [agenticMode, setAgenticMode] = useState<AgenticMode>("thinking");
    const isAgenticMode = searchMode === "agent";

    // Filter state
    const [filterJson, setFilterJson] = useState("");
    const [isFilterValid, setIsFilterValid] = useState(true);

    // Agentic filter builder state
    const [agenticFilterGroups, setAgenticFilterGroups] = useState<FilterGroup[]>([]);
    const [showFilterBuilder, setShowFilterBuilder] = useState(false);

    // API key state
    const [apiKey, setApiKey] = useState<string>("YOUR_API_KEY");

    // Code block modal state
    const [showCodeBlock, setShowCodeBlock] = useState(false);

    // Toggle buttons state
    const [toggles, setToggles] = useState<SearchToggles>({
        queryExpansion: true,
        filter: false,
        queryInterpretation: false,
        reRanking: true,
        answer: true
    });

    // Tooltip management state
    const [openTooltip, setOpenTooltip] = useState<string | null>(null);
    const tooltipTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const [hoveredTooltipContent, setHoveredTooltipContent] = useState<string | null>(null);

    // (Removed) Code button attention nudge state

    // Usage limits: queries
    const [queriesAllowed, setQueriesAllowed] = useState(true);
    const [queriesCheckDetails, setQueriesCheckDetails] = useState<SingleActionCheckResponse | null>(null);
    const [isCheckingUsage, setIsCheckingUsage] = useState(true);

    const [transientIssue, setTransientIssue] = useState<{
        message: string;
        detail?: string | null;
    } | null>(null);

    // Fetch API key on mount
    useEffect(() => {
        const fetchApiKey = async () => {
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
            }
        };

        fetchApiKey();
    }, []);

    // Handle escape key for modal
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && showCodeBlock) {
                setShowCodeBlock(false);
            }
        };

        if (showCodeBlock) {
            document.addEventListener('keydown', handleEscape);
            // Prevent body scroll when modal is open
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }

        // Cleanup
        return () => {
            if (tooltipTimeoutRef.current) {
                clearTimeout(tooltipTimeoutRef.current);
            }
            document.removeEventListener('keydown', handleEscape);
            document.body.style.overflow = '';
        };
    }, [showCodeBlock]);

    // (Removed) Manage periodic halo pulses when eligible

    const hasQuery = query.trim().length > 0;
    const canRetrySearch = Boolean(transientIssue) && !isSearching;
    const activeFilterCount = countActiveFilters(agenticFilterGroups);

    // Streaming controls
    const abortRef = useRef<AbortController | null>(null);
    const searchSeqRef = useRef(0);

    // Cancel current search
    const handleCancelSearch = useCallback(() => {
        console.log('[SearchBox] Cancel requested');
        const controller = abortRef.current;
        if (controller) {
            console.log('[SearchBox] Aborting current stream', { hasController: !!controller, seq: searchSeqRef.current });
            controller.abort();
            // Surface synthetic cancellation events to the parent
            try { onStreamEventProp?.({ type: 'cancelled' } as any); } catch { void 0; }
            try { onStreamUpdateProp?.({ status: 'cancelled' }); } catch { void 0; }
            try { onCancel?.(); } catch { void 0; }
        }
        // Re-check queries allowance after cancellation
        try { void checkQueriesAllowed(); } catch { void 0; }
    }, [onStreamEventProp, onStreamUpdateProp, onCancel]);

    // Check if queries are allowed based on usage limits
    const checkQueriesAllowed = useCallback(async () => {
        try {
            setIsCheckingUsage(true);
            const response = await apiClient.get('/usage/check-action?action=queries');
            if (response.ok) {
                const data: SingleActionCheckResponse = await response.json();
                setQueriesAllowed(data.allowed);
                setQueriesCheckDetails(data);
            } else {
                // Default to allowed on error to not block users
                setQueriesAllowed(true);
                setQueriesCheckDetails(null);
            }
        } catch (error) {
            // Default to allowed on error to not block users
            setQueriesAllowed(true);
            setQueriesCheckDetails(null);
        } finally {
            setIsCheckingUsage(false);
        }
    }, []);

    // Initial usage check on mount
    useEffect(() => {
        void checkQueriesAllowed();
    }, [checkQueriesAllowed]);

    // Main search handler
    const handleSendQuery = useCallback(async () => {
        if (!hasQuery || !collectionId || isSearching || !queriesAllowed || isCheckingUsage || disabled) return;

        // Abort previous stream if any
        if (abortRef.current) {
            abortRef.current.abort();
            abortRef.current = null;
        }

        setTransientIssue(null);

        const mySeq = ++searchSeqRef.current;
        const abortController = new AbortController();
        abortRef.current = abortController;

        // Store the response type being used for this search
        // Agentic mode always generates a completion answer
        const currentResponseType = isAgenticMode ? "completion" : (toggles.answer ? "completion" : "raw");

        setIsSearching(true);
        onSearchStart?.(currentResponseType);

        const startTime = performance.now();

        try {
            // Parse filter if enabled and valid
            let parsedFilter = null;
            if (toggles.filter && filterJson && isFilterValid) {
                try {
                    parsedFilter = JSON.parse(filterJson);
                } catch (e) {
                    console.error("Failed to parse filter JSON:", e);
                    parsedFilter = null;
                }
            }

            // Build request body and stream URL based on search mode
            let requestBody: any;
            let streamUrl: string;

            if (isAgenticMode) {
                // Agentic search: query + optional filters + mode
                requestBody = {
                    query: query,
                    filter: toBackendFilterGroups(agenticFilterGroups),
                    mode: agenticMode,
                };
                streamUrl = `/collections/${collectionId}/agentic-search/stream`;
            } else {
                // Regular pipeline search
                requestBody = {
                    query: query,
                    retrieval_strategy: searchMethod,
                    expand_query: toggles.queryExpansion,
                    interpret_filters: toggles.queryInterpretation,
                    temporal_relevance: 0,  // Feature disabled - under construction
                    rerank: toggles.reRanking,
                    generate_answer: toggles.answer,
                };

                // Add filter only if it's valid
                if (parsedFilter) {
                    requestBody.filter = parsedFilter;
                }

                const debugParams = new URLSearchParams();
                if (typeof window !== 'undefined') {
                    if (window.localStorage.getItem('airweave-debug-force-transient-search-error') === 'true') {
                        debugParams.set('debug_force_transient_error', 'true');
                    }
                    if (window.localStorage.getItem('airweave-debug-force-search-error') === 'true') {
                        debugParams.set('debug_force_search_error', 'true');
                    }
                }
                const debugQuery = debugParams.toString();
                streamUrl = `/collections/${collectionId}/search/stream${debugQuery ? `?${debugQuery}` : ''}`;
            }

            console.log(`[SearchBox] ---- ${isAgenticMode ? 'AGENTIC' : 'REGULAR'} SEARCH ----`);
            console.log(`[SearchBox] URL: POST ${streamUrl}`);
            console.log(`[SearchBox] Body:`, JSON.stringify(requestBody, null, 2));

            // Make the streaming API call
            const response = await apiClient.post(
                streamUrl,
                requestBody,
                { signal: abortController.signal, extraHeaders: {} }
            );

            console.log(`[SearchBox] Response status: ${response.status} ${response.statusText}`);
            console.log(`[SearchBox] Response has body: ${!!response.body}`);

            if (!response.ok || !response.body) {
                const errorText = await response.text().catch(() => "");
                console.error(`[SearchBox] Stream failed (${response.status}):`, errorText);

                // Surface validation errors (422) with the actual message
                if (response.status === 422) {
                    let detail = "Invalid filter configuration.";
                    try {
                        const parsed = JSON.parse(errorText);

                        // Helper: extract human-readable messages from the custom
                        // error_messages / errors shape used by the Airweave middleware.
                        const extractFromErrors = (errArr: any[]): string[] => {
                            const out: string[] = [];
                            for (const entry of errArr) {
                                if (typeof entry === "string") { out.push(entry); continue; }
                                if (typeof entry === "object" && entry !== null) {
                                    for (const v of Object.values(entry)) {
                                        if (typeof v === "string") out.push(v);
                                    }
                                }
                            }
                            return out;
                        };

                        // Dev mode: { error_messages: { errors: [...] }, ... }
                        const errRoot = parsed.error_messages ?? parsed;
                        if (errRoot.errors && Array.isArray(errRoot.errors)) {
                            const msgs = extractFromErrors(errRoot.errors);
                            if (msgs.length) detail = msgs.join("; ");
                        } else if (parsed.detail) {
                            // FastAPI default: { detail: [...] } or { detail: "string" }
                            detail = Array.isArray(parsed.detail)
                                ? parsed.detail.map((d: any) => d.msg ?? JSON.stringify(d)).join("; ")
                                : String(parsed.detail);
                        }
                    } catch { /* use default detail */ }

                    const endTime = performance.now();
                    const responseTime = Math.round(endTime - startTime);
                    onSearch(
                        { error: detail, errorIsTransient: false, status: 422 },
                        currentResponseType,
                        responseTime,
                    );
                    setIsSearching(false);
                    onSearchEnd?.();
                    return;
                }

                throw new Error(errorText || `Stream failed: ${response.status} ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            // Aggregates
            let latestResults: any[] = [];
            let latestCompletion: string | null = null;
            let requestId: string | null = null;
            let phase: StreamPhase = "searching";

            const emitEvent = (event: SearchEvent) => {
                try { onStreamEventProp?.(event); } catch { void 0; }
            };
            const emitUpdate = () => {
                try {
                    onStreamUpdateProp?.({ requestId, results: latestResults, status: phase });
                } catch { void 0; }
            };

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                if (searchSeqRef.current !== mySeq) break; // stale stream

                buffer += decoder.decode(value, { stream: true });
                const frames = buffer.split('\n\n');
                buffer = frames.pop() || "";

                for (const frame of frames) {
                    const dataLines = frame
                        .split('\n')
                        .filter((l) => l.startsWith('data:'))
                        .map((l) => l.slice(5).trim());
                    if (dataLines.length === 0) continue;
                    const payloadStr = dataLines.join('\n');
                    let event: any;
                    try {
                        event = JSON.parse(payloadStr);
                    } catch {
                        console.log(`[SearchBox] SSE non-JSON frame:`, payloadStr);
                        continue; // non-JSON heartbeat or noise
                    }

                    console.log(`[SearchBox] SSE event:`, event.type, event);

                    emitEvent(event as SearchEvent);

                    switch (event.type as SearchEvent['type']) {
                        case 'connected':
                            requestId = event.request_id || requestId;
                            emitUpdate();
                            break;
                        case 'results':
                            if (Array.isArray(event.results)) {
                                latestResults = event.results;
                            }
                            emitUpdate();
                            break;
                        case 'completion_done':
                            // Capture completion when it's generated (not streamed)
                            if (typeof event.text === 'string') {
                                latestCompletion = event.text;
                            }
                            phase = 'answering';
                            emitUpdate();
                            break;
                        case 'error': {
                            const endTime = performance.now();
                            const responseTime = Math.round(endTime - startTime);
                            const errorMessage = event.message || 'Streaming error';
                            if (event.transient === true) {
                                onSearch(
                                    {
                                        error: "Something went wrong, please try again.",
                                        errorIsTransient: true,
                                    },
                                    currentResponseType,
                                    responseTime
                                );
                                setTransientIssue({
                                    message: errorMessage || 'Search connection interrupted. Please try again.',
                                    detail: event.detail,
                                });
                                throw new TransientStreamError(errorMessage);
                            }
                            setTransientIssue(null);
                            onSearch({ error: errorMessage, errorIsTransient: false }, currentResponseType, responseTime);
                            throw new Error(errorMessage);
                        }
                        case 'done': {
                            const endTime = performance.now();
                            const responseTime = Math.round(endTime - startTime);

                            let finalResponse;
                            if (isAgenticMode && event.response) {
                                // Agentic done: extract answer + results from response envelope
                                finalResponse = {
                                    completion: event.response.answer?.text || null,
                                    citations: event.response.answer?.citations || [],
                                    results: event.response.results || [],
                                    responseTime,
                                };
                            } else {
                                // Regular done: assemble from accumulated stream data
                                finalResponse = {
                                    completion: latestCompletion || null,
                                    results: latestResults || [],
                                    responseTime,
                                };
                            }

                            console.log('[SearchBox] Done event - sending final response:', {
                                hasCompletion: !!finalResponse.completion,
                                completionLength: finalResponse.completion?.length,
                                responseType: currentResponseType,
                                resultsCount: finalResponse.results?.length,
                                agentic: isAgenticMode,
                            });
                            onSearch(finalResponse, currentResponseType, responseTime);
                            break;
                        }
                        default:
                            // Forward all other events; no aggregate change
                            break;
                    }
                }
            }
        } catch (error) {
            // Ignore AbortError from cancellations
            const err = error as any;
            if (err instanceof TransientStreamError) {
                console.warn("Transient search stream issue:", err.message);
            } else if (err && (err.name === 'AbortError' || err.message === 'AbortError')) {
                // noop
            } else {
                const endTime = performance.now();
                const responseTime = Math.round(endTime - startTime);
                console.error("Search stream failed:", error);
                const fallbackMessage =
                    error instanceof Error ? error.message : "Search connection interrupted. Please try again.";
                setTransientIssue({
                    message: fallbackMessage,
                });
                onSearch(
                    {
                        error: "Something went wrong, please try again.",
                        errorIsTransient: true,
                    },
                    currentResponseType,
                    responseTime
                );
            }
        } finally {
            // Only end if this is still the active stream
            if (searchSeqRef.current === mySeq) {
                setIsSearching(false);
                onSearchEnd?.();
                // Re-check queries allowance after a search completes
                try { void checkQueriesAllowed(); } catch { void 0; }
                if (abortRef.current === abortController) {
                    abortRef.current = null;
                }
            }
        }
    }, [hasQuery, collectionId, query, searchMethod, toggles, filterJson, isFilterValid, isSearching, onSearch, onSearchStart, onSearchEnd, onStreamEventProp, onStreamUpdateProp, queriesAllowed, isCheckingUsage, disabled, checkQueriesAllowed, searchMode, agenticMode, isAgenticMode]);

    // Handle search method change
    const handleMethodChange = useCallback((newMethod: SearchMethod) => {
        setSearchMethod(newMethod);
        // Disable query expansion for keyword-only search
        // Reason: Expansion only benefits neural/semantic search, not keyword matching
        if (newMethod === "keyword") {
            setToggles(prev => ({ ...prev, queryExpansion: false }));
        }
    }, []);

    // Handle toggle button clicks
    const handleToggle = useCallback((name: keyof SearchToggles, displayName: string) => {
        setToggles(prev => ({
            ...prev,
            [name]: !prev[name]
        }));
    }, []);

    // Tooltip management helpers
    const handleTooltipMouseEnter = useCallback((tooltipId: string) => {
        // Clear any pending timeout
        if (tooltipTimeoutRef.current) {
            clearTimeout(tooltipTimeoutRef.current);
            tooltipTimeoutRef.current = null;
        }
        setOpenTooltip(tooltipId);
    }, []);

    const handleTooltipMouseLeave = useCallback((tooltipId: string) => {
        // Only close if we're not hovering over the tooltip content
        if (hoveredTooltipContent !== tooltipId) {
            // Add a small delay before closing to allow moving to tooltip content
            tooltipTimeoutRef.current = setTimeout(() => {
                setOpenTooltip(prev => prev === tooltipId ? null : prev);
            }, 100);
        }
    }, [hoveredTooltipContent]);

    const handleTooltipContentMouseEnter = useCallback((tooltipId: string) => {
        // Clear any pending timeout
        if (tooltipTimeoutRef.current) {
            clearTimeout(tooltipTimeoutRef.current);
            tooltipTimeoutRef.current = null;
        }
        setHoveredTooltipContent(tooltipId);
        setOpenTooltip(tooltipId);
    }, []);

    const handleTooltipContentMouseLeave = useCallback((tooltipId: string) => {
        setHoveredTooltipContent(null);
        // Close the tooltip after a small delay
        tooltipTimeoutRef.current = setTimeout(() => {
            setOpenTooltip(prev => prev === tooltipId ? null : prev);
        }, 100);
    }, []);

    return (
        <>
            <div className={cn("w-full", className)}>
                {/* Mode toggle (above search box) — only shown when agentic search is enabled */}
                {agenticEnabled && (
                    <div className="flex items-center justify-end gap-2 mb-1.5">
                        <div
                            className={cn(
                                "inline-flex items-center h-6 rounded-md border p-0.5",
                                isDark ? "border-border/50 bg-background" : "border-border bg-white"
                            )}
                        >
                            <button
                                type="button"
                                onClick={() => onSearchModeChange?.("agent")}
                                className={cn(
                                    "h-full px-2 rounded-[4px] text-[11px] font-medium transition-all",
                                    isAgenticMode
                                        ? "text-primary bg-primary/10"
                                        : "text-muted-foreground hover:text-foreground"
                                )}
                            >
                                Agentic Search
                            </button>
                            <button
                                type="button"
                                onClick={() => onSearchModeChange?.("search")}
                                className={cn(
                                    "h-full px-2 rounded-[4px] text-[11px] font-medium transition-all",
                                    !isAgenticMode
                                        ? "text-primary bg-primary/10"
                                        : "text-muted-foreground hover:text-foreground"
                                )}
                            >
                                Classic Search
                            </button>
                        </div>
                    </div>
                )}

                <div
                    className={cn(
                        DESIGN_SYSTEM.radius.card,
                        "border overflow-hidden",
                        isDark ? "border-border bg-gray-900" : "border-border bg-white"
                    )}
                >
                    <div className="relative px-2 pt-2 pb-1">
                        {/* Code button with tooltip */}
                        <TooltipProvider delayDuration={0}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setShowCodeBlock(true);
                                        }}
                                        className={cn(
                                            "absolute top-2 right-2 h-8 w-8 rounded-md border-dashed border shadow-sm flex items-center justify-center transition-all z-20",
                                            isDark
                                                ? "bg-blue-500/10 border-blue-500/30 hover:bg-blue-500/15 hover:border-blue-400/40"
                                                : "bg-blue-50/50 border-blue-400/40 hover:bg-blue-50/70 hover:border-blue-400/50"
                                        )}
                                        title="View integration code"
                                    >
                                        <CodeXml className={cn(
                                            DESIGN_SYSTEM.icons.button,
                                            isDark ? "text-blue-400" : "text-blue-500"
                                        )} />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent
                                    side="left"
                                    sideOffset={8}
                                    className={DESIGN_SYSTEM.tooltip.content}
                                    arrowClassName={DESIGN_SYSTEM.tooltip.arrow}
                                >
                                    <div className="space-y-2">
                                        <div className={DESIGN_SYSTEM.tooltip.title}>Call the Search API</div>
                                        <p className={DESIGN_SYSTEM.tooltip.description}>Open a ready-to-use snippet for JS or Python.</p>
                                        <div className={DESIGN_SYSTEM.tooltip.divider}>
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    setShowCodeBlock(true);
                                                }}
                                                className={DESIGN_SYSTEM.tooltip.link}
                                            >
                                                Open example
                                            </button>
                                        </div>
                                    </div>
                                </TooltipContent>
                            </Tooltip>
                        </TooltipProvider>

                        {(!queriesAllowed || isCheckingUsage || disabled) ? (
                            <TooltipProvider delayDuration={0}>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <div>
                                            <textarea
                                                value={query}
                                                onChange={(e) => setQuery(e.target.value)}
                                                onKeyDown={(e) => {
                                                    if (e.key === "Enter" && !e.shiftKey) {
                                                        if (!hasQuery || isSearching || !queriesAllowed || isCheckingUsage || disabled) return;
                                                        e.preventDefault();
                                                        handleSendQuery();
                                                    }
                                                }}
                                                placeholder={isAgenticMode ? "Ask your agent a question..." : "Ask a question about your data"}
                                                disabled={!queriesAllowed || isCheckingUsage || disabled}
                                                className={cn(
                                                    "w-full h-20 px-2 pr-32 py-1.5 leading-relaxed resize-none overflow-y-auto outline-none rounded-xl bg-transparent",
                                                    DESIGN_SYSTEM.typography.sizes.header,
                                                    isDark ? "placeholder:text-gray-500" : "placeholder:text-gray-500",
                                                    (!queriesAllowed || isCheckingUsage || disabled) && "opacity-60 cursor-not-allowed"
                                                )}
                                            />
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent className="max-w-xs">
                                        <p className={DESIGN_SYSTEM.typography.sizes.body}>
                                            {isCheckingUsage ? (
                                                "Checking usage…"
                                            ) : disabled ? (
                                                "Connect a source to enable search."
                                            ) : queriesCheckDetails?.reason === 'usage_limit_exceeded' ? (
                                                <>
                                                    Query limit reached.{' '}
                                                    <a
                                                        href="/organization/settings?tab=billing"
                                                        className="underline"
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        Upgrade your plan
                                                    </a>
                                                    {' '}to continue searching.
                                                </>
                                            ) : queriesCheckDetails?.reason === 'payment_required' ? (
                                                <>
                                                    Billing issue detected.{' '}
                                                    <a
                                                        href="/organization/settings?tab=billing"
                                                        className="underline"
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        Update billing
                                                    </a>
                                                    {' '}to continue searching.
                                                </>
                                            ) : (
                                                "Search is currently disabled."
                                            )}
                                        </p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        ) : (
                            <textarea
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && !e.shiftKey) {
                                        if (!hasQuery || isSearching || !queriesAllowed || isCheckingUsage || disabled) return;
                                        e.preventDefault();
                                        handleSendQuery();
                                    }
                                }}
                                placeholder={isAgenticMode ? "Ask your agent a question..." : "Ask a question about your data"}
                                className={cn(
                                    "w-full h-20 px-2 pr-32 py-1.5 leading-relaxed resize-none overflow-y-auto outline-none rounded-xl bg-transparent",
                                    DESIGN_SYSTEM.typography.sizes.header,
                                    isDark ? "placeholder:text-gray-500" : "placeholder:text-gray-500"
                                )}
                            />
                        )}
                    </div>
                    <div className={cn(
                        // Compact controls row
                        "flex items-center justify-between px-2 pb-2"
                    )}>
                        {/* Controlled tooltips for instant response */}
                        <TooltipProvider delayDuration={0}>
                            {/* Left side controls */}
                            <div className="flex items-center gap-1.5">
                                {isAgenticMode ? (
                                    <>
                                        {/* Agent mode controls */}

                                        {/* 1. Filter popover */}
                                        <Popover open={showFilterBuilder} onOpenChange={setShowFilterBuilder}>
                                            <PopoverTrigger asChild>
                                                <div className="relative">
                                                    <div
                                                        className={cn(
                                                            DESIGN_SYSTEM.buttons.heights.secondary,
                                                            "w-8 p-0 border cursor-pointer",
                                                            DESIGN_SYSTEM.radius.button,
                                                            activeFilterCount > 0
                                                                ? "border-primary"
                                                                : isDark ? "border-border/50 bg-background" : "border-border bg-white"
                                                        )}
                                                    >
                                                        <button
                                                            type="button"
                                                            className={cn(
                                                                "h-full w-full flex items-center justify-center",
                                                                DESIGN_SYSTEM.radius.button,
                                                                DESIGN_SYSTEM.transitions.standard,
                                                                activeFilterCount > 0
                                                                    ? "text-primary hover:bg-primary/10"
                                                                    : "text-foreground hover:bg-muted"
                                                            )}
                                                        >
                                                            <FiSliders className="h-4 w-4" strokeWidth={1.5} />
                                                        </button>
                                                    </div>
                                                    {activeFilterCount > 0 && (
                                                        <span className={cn(
                                                            "absolute -top-1.5 -right-1.5 h-4 min-w-4 rounded-full",
                                                            "bg-primary text-primary-foreground text-[9px] font-bold",
                                                            "flex items-center justify-center px-1 pointer-events-none"
                                                        )}>
                                                            {activeFilterCount}
                                                        </span>
                                                    )}
                                                </div>
                                            </PopoverTrigger>
                                            <PopoverContent
                                                side="bottom"
                                                align="start"
                                                sideOffset={6}
                                                className={cn(
                                                    "w-[620px] h-[340px] p-0 overflow-hidden",
                                                    isDark ? "bg-background" : "bg-background",
                                                )}
                                            >
                                                <FilterBuilderPopover
                                                    value={agenticFilterGroups}
                                                    onChange={setAgenticFilterGroups}
                                                    onClose={() => setShowFilterBuilder(false)}
                                                />
                                            </PopoverContent>
                                        </Popover>

                                        {/* 2. Thinking mode slider */}
                                        <div
                                            className={cn(
                                                DESIGN_SYSTEM.buttons.heights.secondary,
                                                "inline-flex items-center rounded-md border p-0.5",
                                                isDark ? "border-border/50 bg-background" : "border-border bg-white"
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => setAgenticMode("fast")}
                                                className={cn(
                                                    "h-full px-2 rounded-[4px] text-[11px] font-medium transition-all flex items-center gap-1",
                                                    agenticMode === "fast"
                                                        ? "text-primary bg-primary/10"
                                                        : "text-muted-foreground hover:text-foreground"
                                                )}
                                                title="Single-pass fast search"
                                            >
                                                <Zap className="h-3 w-3" strokeWidth={1.5} />
                                                Fast
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => setAgenticMode("thinking")}
                                                className={cn(
                                                    "h-full px-2 rounded-[4px] text-[11px] font-medium transition-all flex items-center gap-1",
                                                    agenticMode === "thinking"
                                                        ? "text-primary bg-primary/10"
                                                        : "text-muted-foreground hover:text-foreground"
                                                )}
                                                title="Multi-step reasoning search"
                                            >
                                                <Brain className="h-3 w-3" strokeWidth={1.5} />
                                                Thinking
                                            </button>
                                        </div>
                                    </>
                                ) : (
                                <>
                                {/* Regular search controls */}

                                {/* 1. Method segmented control (icons) */}
                                <div className={cn(DESIGN_SYSTEM.buttons.heights.secondary, "inline-block")}>
                                    <div
                                        className={cn(
                                            "relative h-full",
                                            "rounded-md border p-0.5 gap-0.5 overflow-hidden",
                                            "grid grid-cols-3 items-stretch",
                                            isDark ? "border-border/50 bg-background" : "border-border bg-white"
                                        )}
                                    >
                                        {/* HYBRID */}
                                        <Tooltip open={openTooltip === "hybrid"}>
                                            <TooltipTrigger asChild>
                                                <button
                                                    type="button"
                                                    onClick={searchMethod === "hybrid" ? undefined : () => handleMethodChange("hybrid")}
                                                    onMouseEnter={() => handleTooltipMouseEnter("hybrid")}
                                                    onMouseLeave={() => handleTooltipMouseLeave("hybrid")}
                                                    className={cn(
                                                        "aspect-square h-full flex items-center justify-center border",
                                                        DESIGN_SYSTEM.radius.button,
                                                        DESIGN_SYSTEM.transitions.standard,
                                                        searchMethod === "hybrid"
                                                            ? "text-primary border-primary hover:bg-primary/10 cursor-default"
                                                            : "text-foreground border-transparent hover:bg-muted cursor-pointer",
                                                    )}
                                                    title="Hybrid search"
                                                >
                                                    <FiGitMerge className="h-4 w-4" strokeWidth={1.5} />
                                                </button>
                                            </TooltipTrigger>
                                            <TooltipContent
                                                side="bottom"
                                                sideOffset={2}
                                                className={DESIGN_SYSTEM.tooltip.content}
                                                arrowClassName={DESIGN_SYSTEM.tooltip.arrow}
                                                onMouseEnter={() => handleTooltipContentMouseEnter("hybrid")}
                                                onMouseLeave={() => handleTooltipContentMouseLeave("hybrid")}
                                            >
                                                <div className="space-y-2">
                                                    <div className={DESIGN_SYSTEM.tooltip.title}>Search method: Hybrid</div>
                                                    <p className={DESIGN_SYSTEM.tooltip.description}>
                                                        Combines AI semantic and keyword signals for the best overall relevance.
                                                    </p>
                                                    <div className={DESIGN_SYSTEM.tooltip.divider}>
                                                        <a
                                                            href="https://docs.airweave.ai/search#search-method"
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className={DESIGN_SYSTEM.tooltip.link}
                                                        >
                                                            Docs
                                                        </a>
                                                    </div>
                                                </div>
                                            </TooltipContent>
                                        </Tooltip>

                                        {/* NEURAL */}
                                        <Tooltip open={openTooltip === "neural"}>
                                            <TooltipTrigger asChild>
                                                <button
                                                    type="button"
                                                    onClick={searchMethod === "neural" ? undefined : () => handleMethodChange("neural")}
                                                    onMouseEnter={() => handleTooltipMouseEnter("neural")}
                                                    onMouseLeave={() => handleTooltipMouseLeave("neural")}
                                                    className={cn(
                                                        "aspect-square h-full flex items-center justify-center border",
                                                        DESIGN_SYSTEM.radius.button,
                                                        DESIGN_SYSTEM.transitions.standard,
                                                        searchMethod === "neural"
                                                            ? "text-primary border-primary hover:bg-primary/10 cursor-default"
                                                            : "text-foreground border-transparent hover:bg-muted cursor-pointer",
                                                    )}
                                                    title="Neural search"
                                                >
                                                    <ChartScatter className="h-4 w-4" strokeWidth={1.5} />
                                                </button>
                                            </TooltipTrigger>
                                            <TooltipContent
                                                side="bottom"
                                                sideOffset={2}
                                                className={DESIGN_SYSTEM.tooltip.content}
                                                arrowClassName={DESIGN_SYSTEM.tooltip.arrow}
                                                onMouseEnter={() => handleTooltipContentMouseEnter("neural")}
                                                onMouseLeave={() => handleTooltipContentMouseLeave("neural")}
                                            >
                                                <div className="space-y-2">
                                                    <div className={DESIGN_SYSTEM.tooltip.title}>Search method: Neural</div>
                                                    <p className={DESIGN_SYSTEM.tooltip.description}>
                                                        Pure semantic matching using transformer embeddings.
                                                    </p>
                                                    <div className={DESIGN_SYSTEM.tooltip.divider}>
                                                        <a
                                                            href="https://docs.airweave.ai/search#search-method"
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className={DESIGN_SYSTEM.tooltip.link}
                                                        >
                                                            Docs
                                                        </a>
                                                    </div>
                                                </div>
                                            </TooltipContent>
                                        </Tooltip>

                                        {/* KEYWORD */}
                                        <Tooltip open={openTooltip === "keyword"}>
                                            <TooltipTrigger asChild>
                                                <button
                                                    type="button"
                                                    onClick={searchMethod === "keyword" ? undefined : () => handleMethodChange("keyword")}
                                                    onMouseEnter={() => handleTooltipMouseEnter("keyword")}
                                                    onMouseLeave={() => handleTooltipMouseLeave("keyword")}
                                                    className={cn(
                                                        "aspect-square h-full flex items-center justify-center border",
                                                        DESIGN_SYSTEM.radius.button,
                                                        DESIGN_SYSTEM.transitions.standard,
                                                        searchMethod === "keyword"
                                                            ? "text-primary border-primary hover:bg-primary/10 cursor-default"
                                                            : "text-foreground border-transparent hover:bg-muted cursor-pointer",
                                                    )}
                                                    title="Keyword search"
                                                >
                                                    <FiType className="h-4 w-4" strokeWidth={1.5} />
                                                </button>
                                            </TooltipTrigger>
                                            <TooltipContent
                                                side="bottom"
                                                sideOffset={2}
                                                className={DESIGN_SYSTEM.tooltip.content}
                                                arrowClassName={DESIGN_SYSTEM.tooltip.arrow}
                                                onMouseEnter={() => handleTooltipContentMouseEnter("keyword")}
                                                onMouseLeave={() => handleTooltipContentMouseLeave("keyword")}
                                            >
                                                <div className="space-y-2">
                                                    <div className={DESIGN_SYSTEM.tooltip.title}>Search method: Keyword</div>
                                                    <p className={DESIGN_SYSTEM.tooltip.description}>
                                                        BM25 keyword matching for exact term precision.
                                                    </p>
                                                    <div className={DESIGN_SYSTEM.tooltip.divider}>
                                                        <a
                                                            href="https://docs.airweave.ai/search#search-method"
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className={DESIGN_SYSTEM.tooltip.link}
                                                        >
                                                            Docs
                                                        </a>
                                                    </div>
                                                </div>
                                            </TooltipContent>
                                        </Tooltip>
                                    </div>
                                </div>

                                {/* 2. Query expansion (icon) - disabled for keyword-only search */}
                                <Tooltip open={openTooltip === "queryExpansion"}>
                                    <TooltipTrigger asChild>
                                        <div
                                            onMouseEnter={() => handleTooltipMouseEnter("queryExpansion")}
                                            onMouseLeave={() => handleTooltipMouseLeave("queryExpansion")}
                                            className={cn(
                                                DESIGN_SYSTEM.buttons.heights.secondary,
                                                "w-8 p-0 overflow-hidden border",
                                                DESIGN_SYSTEM.radius.button,
                                                searchMethod === "keyword"
                                                    ? (isDark ? "border-border/30 bg-background/50" : "border-border/50 bg-gray-50")
                                                    : toggles.queryExpansion
                                                        ? "border-primary"
                                                        : (isDark ? "border-border/50" : "border-border"),
                                                searchMethod !== "keyword" && (isDark ? "bg-background" : "bg-white")
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    if (searchMethod === "keyword") return; // Disabled for keyword search
                                                    handleToggle("queryExpansion", "query expansion");
                                                }}
                                                disabled={searchMethod === "keyword"}
                                                className={cn(
                                                    "h-full w-full flex items-center justify-center",
                                                    DESIGN_SYSTEM.radius.button,
                                                    DESIGN_SYSTEM.transitions.standard,
                                                    searchMethod === "keyword"
                                                        ? "text-muted-foreground/50 cursor-not-allowed"
                                                        : toggles.queryExpansion
                                                        ? "text-primary hover:bg-primary/10"
                                                        : "text-foreground hover:bg-muted"
                                                )}
                                            >
                                                <FiLayers className="h-4 w-4" strokeWidth={1.5} />
                                            </button>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent
                                        side="bottom"
                                        className={cn(DESIGN_SYSTEM.tooltip.content, "max-w-[220px]")}
                                        arrowClassName={DESIGN_SYSTEM.tooltip.arrow}
                                        onMouseEnter={() => handleTooltipContentMouseEnter("queryExpansion")}
                                        onMouseLeave={() => handleTooltipContentMouseLeave("queryExpansion")}
                                    >
                                        <div className="space-y-2">
                                            <div className={DESIGN_SYSTEM.tooltip.title}>Query expansion</div>
                                            {searchMethod === "keyword" ? (
                                                <p className={DESIGN_SYSTEM.tooltip.description}>
                                                    Not available with keyword search. Switch to hybrid or neural to use query expansion.
                                                </p>
                                            ) : (
                                            <p className={DESIGN_SYSTEM.tooltip.description}>Generates similar versions of your query to improve recall.</p>
                                            )}
                                            <div className={DESIGN_SYSTEM.tooltip.divider}>
                                                <a
                                                    href="https://docs.airweave.ai/search#query-expansion"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className={DESIGN_SYSTEM.tooltip.link}
                                                >
                                                    Docs
                                                </a>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>

                                {/* 3. Filter */}
                                <Tooltip open={openTooltip === "filter"}>
                                    <TooltipTrigger asChild>
                                        <div
                                            onMouseEnter={() => handleTooltipMouseEnter("filter")}
                                            onMouseLeave={() => handleTooltipMouseLeave("filter")}
                                            className={cn(
                                                DESIGN_SYSTEM.buttons.heights.secondary,
                                                "w-8 p-0 overflow-hidden border",
                                                DESIGN_SYSTEM.radius.button,
                                                toggles.filter ? "border-primary" : (isDark ? "border-border/50" : "border-border"),
                                                isDark ? "bg-background" : "bg-white"
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    handleToggle("filter", "filter");
                                                    // Keep tooltip open when enabling
                                                    if (!toggles.filter) {
                                                        setOpenTooltip("filter");
                                                    }
                                                }}
                                                className={cn(
                                                    "h-full w-full flex items-center justify-center",
                                                    DESIGN_SYSTEM.radius.button,
                                                    DESIGN_SYSTEM.transitions.standard,
                                                    toggles.filter
                                                        ? "text-primary hover:bg-primary/10"
                                                        : "text-foreground hover:bg-muted"
                                                )}
                                            >
                                                <FiSliders className="h-4 w-4" strokeWidth={1.5} />
                                            </button>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent
                                        side="bottom"
                                        className={cn(DESIGN_SYSTEM.tooltip.content, "w-[360px] max-w-[90vw]")}
                                        arrowClassName={DESIGN_SYSTEM.tooltip.arrow}
                                        onMouseEnter={() => handleTooltipContentMouseEnter("filter")}
                                        onMouseLeave={() => handleTooltipContentMouseLeave("filter")}
                                    >
                                        <div className="space-y-3">
                                            <div>
                                                <div className={DESIGN_SYSTEM.tooltip.title}>Metadata filtering</div>
                                                <p className={cn(DESIGN_SYSTEM.tooltip.description, "mt-1")}>Filter by fields like source, status, or date before searching.</p>
                                            </div>

                                            <div className="space-y-2">
                                                <div className={cn(DESIGN_SYSTEM.typography.sizes.label, DESIGN_SYSTEM.typography.weights.medium, "text-white/70")}>JSON:</div>
                                                <JsonFilterEditor
                                                    value={filterJson}
                                                    onChange={(value, isValid) => {
                                                        setFilterJson(value);
                                                        setIsFilterValid(isValid);
                                                    }}
                                                    height="160px"
                                                    className=""
                                                />
                                            </div>

                                            <div className={DESIGN_SYSTEM.tooltip.divider}>
                                                <a
                                                    href="https://docs.airweave.ai/search#filtering-results"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className={DESIGN_SYSTEM.tooltip.link}
                                                >
                                                    Docs
                                                </a>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>

                                {/* 4. Query interpretation */}
                                <Tooltip open={openTooltip === "queryInterpretation"}>
                                    <TooltipTrigger asChild>
                                        <div
                                            onMouseEnter={() => handleTooltipMouseEnter("queryInterpretation")}
                                            onMouseLeave={() => handleTooltipMouseLeave("queryInterpretation")}
                                            className={cn(
                                                DESIGN_SYSTEM.buttons.heights.secondary,
                                                "w-8 p-0 overflow-hidden border",
                                                DESIGN_SYSTEM.radius.button,
                                                toggles.queryInterpretation ? "border-primary" : (isDark ? "border-border/50" : "border-border"),
                                                isDark ? "bg-background" : "bg-white"
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => handleToggle("queryInterpretation", "query interpretation")}
                                                className={cn(
                                                    "h-full w-full flex items-center justify-center",
                                                    DESIGN_SYSTEM.radius.button,
                                                    DESIGN_SYSTEM.transitions.standard,
                                                    toggles.queryInterpretation
                                                        ? "text-primary hover:bg-primary/10"
                                                        : "text-foreground hover:bg-muted"
                                                )}
                                            >
                                                <FiFilter className="h-4 w-4" strokeWidth={1.5} />
                                            </button>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent
                                        side="bottom"
                                        className={cn(DESIGN_SYSTEM.tooltip.content, "max-w-[220px]")}
                                        arrowClassName={DESIGN_SYSTEM.tooltip.arrow}
                                        onMouseEnter={() => handleTooltipContentMouseEnter("queryInterpretation")}
                                        onMouseLeave={() => handleTooltipContentMouseLeave("queryInterpretation")}
                                    >
                                        <div className="space-y-2">
                                            <div className={DESIGN_SYSTEM.tooltip.title}>Query interpretation (beta)</div>
                                            <p className={DESIGN_SYSTEM.tooltip.description}>Auto-extracts filters from natural language. May be over‑restrictive.</p>
                                            <div className={DESIGN_SYSTEM.tooltip.divider}>
                                                <a
                                                    href="https://docs.airweave.ai/search#query-interpretation-beta"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className={DESIGN_SYSTEM.tooltip.link}
                                                >
                                                    Docs
                                                </a>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>

                                {/* 5. Re-ranking (Recency bias removed - feature under construction) */}
                                <Tooltip open={openTooltip === "reRanking"}>
                                    <TooltipTrigger asChild>
                                        <div
                                            onMouseEnter={() => handleTooltipMouseEnter("reRanking")}
                                            onMouseLeave={() => handleTooltipMouseLeave("reRanking")}
                                            className={cn(
                                                DESIGN_SYSTEM.buttons.heights.secondary,
                                                "w-8 p-0 overflow-hidden border",
                                                DESIGN_SYSTEM.radius.button,
                                                toggles.reRanking ? "border-primary" : (isDark ? "border-border/50" : "border-border"),
                                                isDark ? "bg-background" : "bg-white"
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => handleToggle("reRanking", "re-ranking")}
                                                className={cn(
                                                    "h-full w-full flex items-center justify-center",
                                                    DESIGN_SYSTEM.radius.button,
                                                    DESIGN_SYSTEM.transitions.standard,
                                                    toggles.reRanking
                                                        ? "text-primary hover:bg-primary/10"
                                                        : "text-foreground hover:bg-muted"
                                                )}
                                            >
                                                <ListStart className="h-4 w-4" strokeWidth={1.5} />
                                            </button>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent
                                        side="bottom"
                                        className={cn(DESIGN_SYSTEM.tooltip.content, "max-w-[220px]")}
                                        arrowClassName={DESIGN_SYSTEM.tooltip.arrow}
                                        onMouseEnter={() => handleTooltipContentMouseEnter("reRanking")}
                                        onMouseLeave={() => handleTooltipContentMouseLeave("reRanking")}
                                    >
                                        <div className="space-y-2">
                                            <div className={DESIGN_SYSTEM.tooltip.title}>AI reranking</div>
                                            <p className={DESIGN_SYSTEM.tooltip.description}>LLM reorders results for better relevance.</p>
                                            <div className={DESIGN_SYSTEM.tooltip.divider}>
                                                <a
                                                    href="https://docs.airweave.ai/search#ai-reranking"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className={DESIGN_SYSTEM.tooltip.link}
                                                >
                                                    Docs
                                                </a>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>

                                {/* 7. Answer */}
                                <Tooltip open={openTooltip === "answer"}>
                                    <TooltipTrigger asChild>
                                        <div
                                            onMouseEnter={() => handleTooltipMouseEnter("answer")}
                                            onMouseLeave={() => handleTooltipMouseLeave("answer")}
                                            className={cn(
                                                DESIGN_SYSTEM.buttons.heights.secondary,
                                                "w-8 p-0 overflow-hidden border",
                                                DESIGN_SYSTEM.radius.button,
                                                toggles.answer ? "border-primary" : (isDark ? "border-border/50" : "border-border"),
                                                isDark ? "bg-background" : "bg-white"
                                            )}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => handleToggle("answer", "answer")}
                                                className={cn(
                                                    "h-full w-full flex items-center justify-center",
                                                    DESIGN_SYSTEM.radius.button,
                                                    DESIGN_SYSTEM.transitions.standard,
                                                    toggles.answer
                                                        ? "text-primary hover:bg-primary/10"
                                                        : "text-foreground hover:bg-muted"
                                                )}
                                            >
                                                <FiMessageSquare className="h-4 w-4" strokeWidth={1.5} />
                                            </button>
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent
                                        side="bottom"
                                        className={cn(DESIGN_SYSTEM.tooltip.content, "max-w-[220px]")}
                                        arrowClassName={DESIGN_SYSTEM.tooltip.arrow}
                                        onMouseEnter={() => handleTooltipContentMouseEnter("answer")}
                                        onMouseLeave={() => handleTooltipContentMouseLeave("answer")}
                                    >
                                        <div className="space-y-2">
                                            <div className={DESIGN_SYSTEM.tooltip.title}>Generate answer</div>
                                            <p className={DESIGN_SYSTEM.tooltip.description}>Returns an AI-written answer instead of raw results when enabled.</p>
                                            <div className={DESIGN_SYSTEM.tooltip.divider}>
                                                <a
                                                    href="https://docs.airweave.ai/search#generate-ai-answers"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className={DESIGN_SYSTEM.tooltip.link}
                                                >
                                                    Docs
                                                </a>
                                            </div>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>
                                </>
                                )}
                            </div>

                            {/* Right side send button with usage gating */}
                            <TooltipProvider delayDuration={0}>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <button
                                            type="button"
                                            onClick={() => {
                                                if (isSearching) {
                                                    handleCancelSearch();
                                                    return;
                                                }
                                                if (canRetrySearch) {
                                                    setTransientIssue(null);
                                                }
                                                void handleSendQuery();
                                            }}
                                            disabled={isSearching ? false : (!hasQuery || !queriesAllowed || isCheckingUsage || disabled)}
                                            className={cn(
                                                "h-8 w-8 rounded-md border shadow-sm flex items-center justify-center transition-all",
                                                isSearching
                                                    ? isDark
                                                        ? "bg-red-900/30 border-red-700 hover:bg-red-900/50 cursor-pointer"
                                                        : "bg-red-50 border-red-200 hover:bg-red-100 cursor-pointer"
                                                    : canRetrySearch
                                                        ? (isDark
                                                            ? "bg-gray-800 border-border hover:bg-muted text-foreground border-gray-700"
                                                            : "bg-white border-border hover:bg-muted text-foreground")
                                                        : (hasQuery && queriesAllowed && !isCheckingUsage && !disabled)
                                                            ? (isDark
                                                                ? "bg-gray-800 border-border hover:bg-muted text-foreground border-gray-700"
                                                                : "bg-white border-border hover:bg-muted text-foreground")
                                                            : (isDark
                                                                ? "bg-muted text-muted-foreground cursor-not-allowed"
                                                                : "bg-muted text-muted-foreground cursor-not-allowed")
                                            )}
                                            title={isSearching
                                                ? "Stop search"
                                                : canRetrySearch
                                                    ? (transientIssue?.message || "Connection interrupted. Click to retry.")
                                                    : (disabled
                                                        ? "Connect a source to enable search."
                                                        : (!hasQuery
                                                            ? "Type a question to enable"
                                                            : (!queriesAllowed
                                                                ? "Query limit reached — upgrade to run searches"
                                                                : (isCheckingUsage ? "Checking usage..." : "Send query"))))}
                                        >
                                            {isSearching ? (
                                                <Square className={cn(DESIGN_SYSTEM.icons.button, "text-red-500")} />
                                            ) : canRetrySearch ? (
                                                <RefreshCw className={cn(DESIGN_SYSTEM.icons.button, "text-muted-foreground")} />
                                            ) : (
                                                <ArrowUp className={DESIGN_SYSTEM.icons.button} />
                                            )}
                                        </button>
                                    </TooltipTrigger>
                                    {!queriesAllowed && queriesCheckDetails?.reason === 'usage_limit_exceeded' && (
                                        <TooltipContent className="max-w-xs">
                                            <p className={DESIGN_SYSTEM.typography.sizes.body}>
                                                Query limit reached.{' '}
                                                <a
                                                    href="/organization/settings?tab=billing"
                                                    className="underline"
                                                    onClick={(e) => e.stopPropagation()}
                                                >
                                                    Upgrade your plan
                                                </a>
                                                {' '}to continue searching.
                                            </p>
                                        </TooltipContent>
                                    )}
                                    {!queriesAllowed && queriesCheckDetails?.reason === 'payment_required' && (
                                        <TooltipContent className="max-w-xs">
                                            <p className={DESIGN_SYSTEM.typography.sizes.body}>
                                                Billing issue detected.{' '}
                                                <a
                                                    href="/organization/settings?tab=billing"
                                                    className="underline"
                                                    onClick={(e) => e.stopPropagation()}
                                                >
                                                    Update billing
                                                </a>
                                                {' '}to continue searching.
                                            </p>
                                        </TooltipContent>
                                    )}
                                </Tooltip>
                            </TooltipProvider>
                        </TooltipProvider>
                    </div>
                </div>
            </div>

            {/* Code Block Modal Overlay */}
            {showCodeBlock && collectionId && (
                <>
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 bg-black/60 z-40 backdrop-blur-sm"
                        onClick={() => setShowCodeBlock(false)}
                    />

                    {/* Modal Content */}
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-8 pointer-events-none">
                        <div
                            className={cn(
                                "relative w-full max-w-4xl pointer-events-auto"
                            )}
                            onClick={(e) => e.stopPropagation()}
                        >
                            {/* Close button */}
                            <button
                                onClick={() => setShowCodeBlock(false)}
                                className={cn(
                                    "absolute top-2 right-2 z-10 h-8 w-8 rounded-md flex items-center justify-center",
                                    "transition-colors",
                                    isDark
                                        ? "bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground"
                                        : "bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground"
                                )}
                                title="Close (Esc)"
                            >
                                <X className="h-4 w-4" />
                            </button>

                            {/* Just the ApiIntegrationDoc Component */}
                            <ApiIntegrationDoc
                                collectionReadableId={collectionId}
                                query={query || "Ask a question about your data"}
                                {...(isAgenticMode
                                    ? {
                                          agenticConfig: {
                                              mode: agenticMode,
                                              filter: toBackendFilterGroups(agenticFilterGroups),
                                          },
                                      }
                                    : {
                                          searchConfig: {
                                              search_method: searchMethod,
                                              expansion_strategy: toggles.queryExpansion ? "auto" : "no_expansion",
                                              enable_query_interpretation: toggles.queryInterpretation,
                                              recency_bias: 0,
                                              enable_reranking: toggles.reRanking,
                                              response_type: toggles.answer ? "completion" : "raw",
                                          },
                                          filter: toggles.filter ? filterJson : null,
                                      }
                                )}
                                apiKey={apiKey}
                            />
                        </div>
                    </div>
                </>
            )}
        </>
    );
};
