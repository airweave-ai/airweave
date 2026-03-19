import { useEffect, useState, useCallback, useRef } from "react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { ArrowUp, CodeXml, X, Square, RefreshCw, Zap, Search, MousePointer2 } from "lucide-react";
import { SlidersHorizontal } from "lucide-react";
import { ApiIntegrationDoc } from "@/search/CodeBlock";
import { FilterBuilderPopover, FilterGroup, toBackendFilterGroups, countActiveFilters } from "@/search/FilterBuilderModal";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { apiClient } from "@/lib/api";
import type { SearchEvent, PartialStreamUpdate, StreamPhase } from "@/search/types";
import { DESIGN_SYSTEM } from "@/lib/design-system";
import { SingleActionCheckResponse } from "@/types";

// Search tier — maps to the three backend endpoint tiers
export type SearchTier = "instant" | "classic" | "agentic";

// Retrieval strategy for instant tier
type RetrievalStrategy = "hybrid" | "semantic" | "keyword";

// Search configuration interface (for code block)
export interface SearchConfig {
    search_method: RetrievalStrategy;
    expansion_strategy: "auto" | "no_expansion";
    enable_query_interpretation: boolean;
    recency_bias: number;
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
    disabled?: boolean;
    onStreamEvent?: (event: SearchEvent) => void;
    onStreamUpdate?: (partial: PartialStreamUpdate) => void;
    onCancel?: () => void;
    agenticEnabled?: boolean;
    tier?: SearchTier;
    onTierChange?: (tier: SearchTier) => void;
}

class TransientStreamError extends Error {
    constructor(message?: string) {
        super(message);
        this.name = "TransientStreamError";
    }
}

// Tier configuration
const TIER_CONFIG = {
    instant: {
        icon: Zap,
        label: "Instant",
        placeholder: "Ask a question about your data",
        tooltip: "Direct vector search",
        timing: "~0.5s",
    },
    classic: {
        icon: Search,
        label: "Classic",
        placeholder: "Ask a question about your data",
        tooltip: "AI-optimized search strategy",
        timing: "~2s",
    },
    agentic: {
        icon: MousePointer2,
        label: "Agentic",
        placeholder: "Ask a question about your data",
        tooltip: "Agent that navigates through your collection to find the best results",
        timing: "<2 min",
    },
} as const;

const TIERS: SearchTier[] = ["instant", "classic", "agentic"];

/**
 * SearchBox Component
 *
 * Simplified search interface with 3-tier selector (instant/classic/agentic),
 * contextual controls per tier, and unified filter builder.
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
    tier = "classic",
    onTierChange,
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    // Core state
    const [query, setQuery] = useState("");
    const [isSearching, setIsSearching] = useState(false);

    // Tier-specific state
    const [retrievalStrategy, setRetrievalStrategy] = useState<RetrievalStrategy>("hybrid");
    const [thinking, setThinking] = useState(false);

    // Filter state (shared across all tiers)
    const [filterGroups, setFilterGroups] = useState<FilterGroup[]>([]);
    const [showFilterBuilder, setShowFilterBuilder] = useState(false);

    // API key state (for code block)
    const [apiKey, setApiKey] = useState<string>("YOUR_API_KEY");
    const [showCodeBlock, setShowCodeBlock] = useState(false);

    // Usage limits
    const [usageAllowed, setUsageAllowed] = useState(true);
    const [usageCheckDetails, setUsageCheckDetails] = useState<SingleActionCheckResponse | null>(null);
    const [isCheckingUsage, setIsCheckingUsage] = useState(true);

    const [transientIssue, setTransientIssue] = useState<{
        message: string;
        detail?: string | null;
    } | null>(null);

    // Tooltip state
    const [openTooltip, setOpenTooltip] = useState<string | null>(null);
    const tooltipTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const [hoveredTooltipContent, setHoveredTooltipContent] = useState<string | null>(null);

    // Streaming controls
    const abortRef = useRef<AbortController | null>(null);
    const searchSeqRef = useRef(0);

    const hasQuery = query.trim().length > 0;
    const canRetrySearch = Boolean(transientIssue) && !isSearching;
    const activeFilterCount = countActiveFilters(filterGroups);

    // Fetch API key on mount
    useEffect(() => {
        const fetchApiKey = async () => {
            try {
                const response = await apiClient.get("/api-keys");
                if (response.ok) {
                    const data = await response.json();
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

    // Handle escape key for code block modal
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && showCodeBlock) {
                setShowCodeBlock(false);
            }
        };
        if (showCodeBlock) {
            document.addEventListener('keydown', handleEscape);
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
        return () => {
            if (tooltipTimeoutRef.current) clearTimeout(tooltipTimeoutRef.current);
            document.removeEventListener('keydown', handleEscape);
            document.body.style.overflow = '';
        };
    }, [showCodeBlock]);

    // Cancel current search
    const handleCancelSearch = useCallback(() => {
        const controller = abortRef.current;
        if (controller) {
            controller.abort();
            try { onStreamEventProp?.({ type: 'cancelled' } as any); } catch { void 0; }
            try { onStreamUpdateProp?.({ status: 'cancelled' }); } catch { void 0; }
            try { onCancel?.(); } catch { void 0; }
        }
        try { void checkUsageAllowed(); } catch { void 0; }
    }, [onStreamEventProp, onStreamUpdateProp, onCancel]);

    // Check usage limits — tier-aware (tokens for agentic, queries for instant/classic)
    const checkUsageAllowed = useCallback(async () => {
        try {
            setIsCheckingUsage(true);
            const actionToCheck = tier === 'agentic' ? 'tokens' : 'queries';
            const response = await apiClient.get(`/usage/check-action?action=${actionToCheck}`);
            if (response.ok) {
                const data: SingleActionCheckResponse = await response.json();
                setUsageAllowed(data.allowed);
                setUsageCheckDetails(data);
            } else {
                setUsageAllowed(true);
                setUsageCheckDetails(null);
            }
        } catch {
            setUsageAllowed(true);
            setUsageCheckDetails(null);
        } finally {
            setIsCheckingUsage(false);
        }
    }, [tier]);

    useEffect(() => { void checkUsageAllowed(); }, [checkUsageAllowed]);

    // Main search handler — routes to v2 endpoints based on tier
    const handleSendQuery = useCallback(async () => {
        if (!hasQuery || !collectionId || isSearching || !usageAllowed || isCheckingUsage || disabled) return;

        if (abortRef.current) {
            abortRef.current.abort();
            abortRef.current = null;
        }

        setTransientIssue(null);

        const mySeq = ++searchSeqRef.current;
        const abortController = new AbortController();
        abortRef.current = abortController;

        // Agentic always returns completion-style response; instant and classic return raw
        const currentResponseType = tier === "agentic" ? "completion" : "raw";

        setIsSearching(true);
        onSearchStart?.(currentResponseType);

        const startTime = performance.now();

        try {
            // Build request body and URL based on tier
            let requestBody: any;
            let streamUrl: string;
            const backendFilters = toBackendFilterGroups(filterGroups);
            const hasFilters = backendFilters.length > 0;

            switch (tier) {
                case "instant":
                    requestBody = {
                        query: query,
                        retrieval_strategy: retrievalStrategy,
                        ...(hasFilters && { filter: backendFilters }),
                    };
                    streamUrl = `/collections/${collectionId}/search/instant`;
                    break;

                case "classic":
                    requestBody = {
                        query: query,
                        ...(hasFilters && { filter: backendFilters }),
                    };
                    streamUrl = `/collections/${collectionId}/search/classic`;
                    break;

                case "agentic":
                    requestBody = {
                        query: query,
                        thinking: thinking,
                        ...(hasFilters && { filter: backendFilters }),
                    };
                    streamUrl = `/collections/${collectionId}/search/agentic/stream`;
                    break;
            }

            console.log(`[SearchBox] ---- ${tier.toUpperCase()} SEARCH ----`);
            console.log(`[SearchBox] URL: POST ${streamUrl}`);
            console.log(`[SearchBox] Body:`, JSON.stringify(requestBody, null, 2));

            const response = await apiClient.post(
                streamUrl,
                requestBody,
                { signal: abortController.signal, extraHeaders: {} }
            );

            if (!response.ok || !response.body) {
                const errorText = await response.text().catch(() => "");
                console.error(`[SearchBox] Request failed (${response.status}):`, errorText);

                if (response.status === 422) {
                    let detail = "Invalid request.";
                    try {
                        const parsed = JSON.parse(errorText);
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
                        const errRoot = parsed.error_messages ?? parsed;
                        if (errRoot.errors && Array.isArray(errRoot.errors)) {
                            const msgs = extractFromErrors(errRoot.errors);
                            if (msgs.length) detail = msgs.join("; ");
                        } else if (parsed.detail) {
                            detail = Array.isArray(parsed.detail)
                                ? parsed.detail.map((d: any) => d.msg ?? JSON.stringify(d)).join("; ")
                                : String(parsed.detail);
                        }
                    } catch { /* use default detail */ }

                    const endTime = performance.now();
                    onSearch({ error: detail, errorIsTransient: false, status: 422 }, currentResponseType, Math.round(endTime - startTime));
                    setIsSearching(false);
                    onSearchEnd?.();
                    return;
                }

                // Try to extract a meaningful error message from the response
                let errorMessage = `Request failed: ${response.status} ${response.statusText}`;
                try {
                    const parsed = JSON.parse(errorText);
                    if (parsed.detail) errorMessage = String(parsed.detail);
                    else if (parsed.message) errorMessage = String(parsed.message);
                } catch {
                    if (errorText) errorMessage = errorText;
                }
                const endTime = performance.now();
                onSearch({ error: errorMessage, errorIsTransient: false, status: response.status }, currentResponseType, Math.round(endTime - startTime));
                return;
            }

            // For instant and classic, the response is JSON (not streaming)
            if (tier !== "agentic") {
                const data = await response.json();
                const endTime = performance.now();
                const responseTime = Math.round(endTime - startTime);
                onSearch({ results: data.results || [], responseTime }, currentResponseType, responseTime);
                return;
            }

            // Agentic: stream SSE events
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let requestId: string | null = null;
            const phase: StreamPhase = "searching";

            const emitEvent = (event: SearchEvent) => {
                try { onStreamEventProp?.(event); } catch { void 0; }
            };
            const emitUpdate = () => {
                try { onStreamUpdateProp?.({ requestId, status: phase }); } catch { void 0; }
            };

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                if (searchSeqRef.current !== mySeq) break;

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
                        continue;
                    }

                    emitEvent(event as SearchEvent);

                    switch (event.type) {
                        case 'started':
                            requestId = event.request_id || requestId;
                            emitUpdate();
                            break;
                        case 'thinking':
                        case 'tool_call':
                        case 'reranking':
                            // Events flow to trace via emitEvent above
                            break;
                        case 'error': {
                            const endTime = performance.now();
                            const responseTime = Math.round(endTime - startTime);
                            const errorMessage = event.message || 'Search failed';
                            setTransientIssue(null);
                            onSearch({ error: errorMessage, errorIsTransient: false }, currentResponseType, responseTime);
                            // Don't throw — the error is already set on searchResponse.
                            // Breaking out of the read loop is handled by the reader finishing.
                            return;
                        }
                        case 'done': {
                            const endTime = performance.now();
                            const responseTime = Math.round(endTime - startTime);
                            onSearch({
                                results: event.results || [],
                                responseTime,
                            }, currentResponseType, responseTime);
                            break;
                        }
                        default:
                            break;
                    }
                }
            }
        } catch (error) {
            const err = error as any;
            if (err instanceof TransientStreamError) {
                console.warn("Transient search stream issue:", err.message);
            } else if (err && (err.name === 'AbortError' || err.message === 'AbortError')) {
                // noop
            } else {
                const endTime = performance.now();
                const responseTime = Math.round(endTime - startTime);
                setTransientIssue({ message: error instanceof Error ? error.message : "Search connection interrupted." });
                onSearch({ error: "Something went wrong, please try again.", errorIsTransient: true }, currentResponseType, responseTime);
            }
        } finally {
            if (searchSeqRef.current === mySeq) {
                setIsSearching(false);
                onSearchEnd?.();
                try { void checkUsageAllowed(); } catch { void 0; }
                if (abortRef.current === abortController) abortRef.current = null;
            }
        }
    }, [hasQuery, collectionId, query, tier, retrievalStrategy, thinking, filterGroups, isSearching, onSearch, onSearchStart, onSearchEnd, onStreamEventProp, onStreamUpdateProp, usageAllowed, isCheckingUsage, disabled, checkUsageAllowed]);

    // Tooltip helpers
    const handleTooltipMouseEnter = useCallback((tooltipId: string) => {
        if (tooltipTimeoutRef.current) { clearTimeout(tooltipTimeoutRef.current); tooltipTimeoutRef.current = null; }
        setOpenTooltip(tooltipId);
    }, []);

    const handleTooltipMouseLeave = useCallback((tooltipId: string) => {
        if (hoveredTooltipContent !== tooltipId) {
            tooltipTimeoutRef.current = setTimeout(() => { setOpenTooltip(prev => prev === tooltipId ? null : prev); }, 100);
        }
    }, [hoveredTooltipContent]);

    const handleTooltipContentMouseEnter = useCallback((tooltipId: string) => {
        if (tooltipTimeoutRef.current) { clearTimeout(tooltipTimeoutRef.current); tooltipTimeoutRef.current = null; }
        setHoveredTooltipContent(tooltipId);
        setOpenTooltip(tooltipId);
    }, []);

    const handleTooltipContentMouseLeave = useCallback((tooltipId: string) => {
        setHoveredTooltipContent(null);
        tooltipTimeoutRef.current = setTimeout(() => { setOpenTooltip(prev => prev === tooltipId ? null : prev); }, 100);
    }, []);

    // Current tier config
    const currentTier = TIER_CONFIG[tier];

    return (
        <>
            <div className={cn("w-full", className)}>
                <div
                    className={cn(
                        DESIGN_SYSTEM.radius.card,
                        "border overflow-hidden",
                        isDark ? "border-border bg-gray-900" : "border-border bg-white"
                    )}
                >
                    {/* Textarea + code button */}
                    <div className="relative px-2 pt-2 pb-1">
                        {/* Code button (top-right) */}
                        <TooltipProvider delayDuration={0}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button
                                        type="button"
                                        onClick={() => setShowCodeBlock(true)}
                                        className={cn(
                                            "absolute top-2 right-2 h-8 w-8 rounded-md border-dashed border shadow-sm flex items-center justify-center transition-all z-20",
                                            isDark
                                                ? "bg-blue-500/10 border-blue-500/30 hover:bg-blue-500/15 hover:border-blue-400/40"
                                                : "bg-blue-50/50 border-blue-400/40 hover:bg-blue-50/70 hover:border-blue-400/50"
                                        )}
                                        title="View integration code"
                                    >
                                        <CodeXml className={cn(DESIGN_SYSTEM.icons.button, isDark ? "text-blue-400" : "text-blue-500")} />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="left" sideOffset={8} className={DESIGN_SYSTEM.tooltip.content} arrowClassName={DESIGN_SYSTEM.tooltip.arrow}>
                                    <div className="space-y-2">
                                        <div className={DESIGN_SYSTEM.tooltip.title}>Call the Search API</div>
                                        <p className={DESIGN_SYSTEM.tooltip.description}>Open a ready-to-use snippet for JS or Python.</p>
                                    </div>
                                </TooltipContent>
                            </Tooltip>
                        </TooltipProvider>

                        {/* Query textarea */}
                        {(!usageAllowed || isCheckingUsage || disabled) ? (
                            <TooltipProvider delayDuration={0}>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <div>
                                            <textarea
                                                value={query}
                                                onChange={(e) => setQuery(e.target.value)}
                                                onKeyDown={(e) => {
                                                    if (e.key === "Enter" && !e.shiftKey) {
                                                        if (!hasQuery || isSearching || !usageAllowed || isCheckingUsage || disabled) return;
                                                        e.preventDefault();
                                                        handleSendQuery();
                                                    }
                                                }}
                                                placeholder={currentTier.placeholder}
                                                disabled={!usageAllowed || isCheckingUsage || disabled}
                                                className={cn(
                                                    "w-full h-20 px-2 pr-32 py-1.5 leading-relaxed resize-none overflow-y-auto outline-none rounded-xl bg-transparent",
                                                    DESIGN_SYSTEM.typography.sizes.header,
                                                    "placeholder:text-gray-500",
                                                    "opacity-60 cursor-not-allowed"
                                                )}
                                            />
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent className="max-w-xs">
                                        <p className={DESIGN_SYSTEM.typography.sizes.body}>
                                            {isCheckingUsage ? "Checking usage…" :
                                             disabled ? "Connect a source to enable search." :
                                             usageCheckDetails?.reason === 'usage_limit_exceeded' ? (
                                                <>{tier === 'agentic' ? 'Token' : 'Query'} limit reached. <a href="/organization/settings?tab=billing" className="underline">Upgrade your plan</a> to continue.</>
                                             ) : usageCheckDetails?.reason === 'payment_required' ? (
                                                <>Billing issue. <a href="/organization/settings?tab=billing" className="underline">Update billing</a> to continue.</>
                                             ) : "Search is currently disabled."}
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
                                        if (!hasQuery || isSearching || !usageAllowed || isCheckingUsage || disabled) return;
                                        e.preventDefault();
                                        handleSendQuery();
                                    }
                                }}
                                placeholder={currentTier.placeholder}
                                className={cn(
                                    "w-full h-20 px-2 pr-32 py-1.5 leading-relaxed resize-none overflow-y-auto outline-none rounded-xl bg-transparent",
                                    DESIGN_SYSTEM.typography.sizes.header,
                                    "placeholder:text-gray-500"
                                )}
                            />
                        )}
                    </div>

                    {/* Controls row */}
                    <div className="flex items-center justify-between px-2 pb-2">
                        <TooltipProvider delayDuration={0}>
                            <div className="flex items-center gap-1.5">
                                {/* ── Tier selector (3-position segmented control) ── */}
                                <div className={cn(
                                    DESIGN_SYSTEM.buttons.heights.secondary,
                                    "inline-flex items-center rounded-md border p-0.5",
                                    isDark ? "border-border/50 bg-background" : "border-border bg-white"
                                )}>
                                    {TIERS.map((t) => {
                                        // Hide agentic if not enabled
                                        if (t === "agentic" && !agenticEnabled) return null;
                                        const config = TIER_CONFIG[t];
                                        const Icon = config.icon;
                                        const isActive = tier === t;
                                        return (
                                            <Tooltip key={t} open={openTooltip === `tier-${t}`}>
                                                <TooltipTrigger asChild>
                                                    <button
                                                        type="button"
                                                        onClick={() => onTierChange?.(t)}
                                                        onMouseEnter={() => handleTooltipMouseEnter(`tier-${t}`)}
                                                        onMouseLeave={() => handleTooltipMouseLeave(`tier-${t}`)}
                                                        className={cn(
                                                            "h-full px-2 rounded-[4px] transition-all flex items-center justify-center",
                                                            isActive
                                                                ? "text-primary bg-primary/10"
                                                                : "text-muted-foreground hover:text-foreground"
                                                        )}
                                                    >
                                                        <Icon className="h-3.5 w-3.5" strokeWidth={1.5} />
                                                    </button>
                                                </TooltipTrigger>
                                                <TooltipContent
                                                    side="bottom"
                                                    sideOffset={4}
                                                    className={cn(DESIGN_SYSTEM.tooltip.content, "max-w-[240px]")}
                                                    arrowClassName={DESIGN_SYSTEM.tooltip.arrow}
                                                    onMouseEnter={() => handleTooltipContentMouseEnter(`tier-${t}`)}
                                                    onMouseLeave={() => handleTooltipContentMouseLeave(`tier-${t}`)}
                                                >
                                                    <div className="space-y-1.5">
                                                        <div className={DESIGN_SYSTEM.tooltip.title}>{config.label}</div>
                                                        <p className={DESIGN_SYSTEM.tooltip.description}>{config.tooltip}</p>
                                                        <p className={cn(DESIGN_SYSTEM.tooltip.description, "font-semibold")}>{config.timing}</p>
                                                    </div>
                                                </TooltipContent>
                                            </Tooltip>
                                        );
                                    })}
                                </div>

                                {/* ── Filter button (always visible) ── */}
                                <Popover open={showFilterBuilder} onOpenChange={setShowFilterBuilder}>
                                    <PopoverTrigger asChild>
                                        <div className="relative">
                                            <div className={cn(
                                                DESIGN_SYSTEM.buttons.heights.secondary,
                                                "w-8 p-0 border cursor-pointer",
                                                DESIGN_SYSTEM.radius.button,
                                                activeFilterCount > 0
                                                    ? "border-primary"
                                                    : isDark ? "border-border/50 bg-background" : "border-border bg-white"
                                            )}>
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
                                                    <SlidersHorizontal className="h-4 w-4" strokeWidth={1.5} />
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
                                        className={cn("w-[620px] h-[340px] p-0 overflow-hidden", isDark ? "bg-background" : "bg-background")}
                                    >
                                        <FilterBuilderPopover
                                            value={filterGroups}
                                            onChange={setFilterGroups}
                                            onClose={() => setShowFilterBuilder(false)}
                                        />
                                    </PopoverContent>
                                </Popover>

                                {/* ── Contextual controls (fade in/out based on tier) ── */}

                                {/* Instant: Retrieval strategy */}
                                {tier === "instant" && (
                                    <div className={cn(
                                        "animate-in fade-in slide-in-from-left-2 duration-200",
                                        DESIGN_SYSTEM.buttons.heights.secondary,
                                        "inline-flex items-center rounded-md border p-0.5",
                                        isDark ? "border-border/50 bg-background" : "border-border bg-white"
                                    )}>
                                        {(["semantic", "hybrid", "keyword"] as RetrievalStrategy[]).map((strategy) => {
                                            const label = strategy === "semantic" ? "Semantic" : strategy === "hybrid" ? "Hybrid" : "Keyword";
                                            const isActive = retrievalStrategy === strategy;
                                            return (
                                                <button
                                                    key={strategy}
                                                    type="button"
                                                    onClick={() => setRetrievalStrategy(strategy)}
                                                    className={cn(
                                                        "h-full px-2 rounded-[4px] text-[11px] font-normal transition-all flex items-center",
                                                        isActive
                                                            ? "text-primary bg-primary/10"
                                                            : "text-muted-foreground hover:text-foreground"
                                                    )}
                                                >
                                                    {label}
                                                </button>
                                            );
                                        })}
                                    </div>
                                )}

                                {/* Agentic: Thinking toggle */}
                                {tier === "agentic" && (
                                    <Tooltip open={openTooltip === "thinking"}>
                                        <TooltipTrigger asChild>
                                            <button
                                                type="button"
                                                onClick={() => setThinking(prev => !prev)}
                                                onMouseEnter={() => handleTooltipMouseEnter("thinking")}
                                                onMouseLeave={() => handleTooltipMouseLeave("thinking")}
                                                className={cn(
                                                    "animate-in fade-in slide-in-from-left-2 duration-200",
                                                    DESIGN_SYSTEM.buttons.heights.secondary,
                                                    "px-2 border",
                                                    DESIGN_SYSTEM.radius.button,
                                                    "text-[11px] font-normal transition-all flex items-center gap-1",
                                                    thinking
                                                        ? "text-primary border-primary bg-primary/10"
                                                        : isDark
                                                            ? "text-muted-foreground hover:text-foreground border-border/50 bg-background hover:bg-muted"
                                                            : "text-muted-foreground hover:text-foreground border-border bg-white hover:bg-muted"
                                                )}
                                            >
                                                Thinking
                                            </button>
                                        </TooltipTrigger>
                                        <TooltipContent
                                            side="bottom"
                                            sideOffset={4}
                                            className={cn(DESIGN_SYSTEM.tooltip.content, "max-w-[240px]")}
                                            arrowClassName={DESIGN_SYSTEM.tooltip.arrow}
                                            onMouseEnter={() => handleTooltipContentMouseEnter("thinking")}
                                            onMouseLeave={() => handleTooltipContentMouseLeave("thinking")}
                                        >
                                            <div className="space-y-1.5">
                                                <div className={DESIGN_SYSTEM.tooltip.title}>Thinking</div>
                                                <p className={DESIGN_SYSTEM.tooltip.description}>
                                                    Extended reasoning, the agent thinks more carefully
                                                </p>
                                                <p className={cn(DESIGN_SYSTEM.tooltip.description, "font-semibold")}>&lt;5 min</p>
                                            </div>
                                        </TooltipContent>
                                    </Tooltip>
                                )}
                            </div>

                            {/* Right side: send button */}
                            <TooltipProvider delayDuration={0}>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <button
                                            type="button"
                                            onClick={() => {
                                                if (isSearching) { handleCancelSearch(); return; }
                                                if (canRetrySearch) setTransientIssue(null);
                                                void handleSendQuery();
                                            }}
                                            disabled={isSearching ? false : (!hasQuery || !usageAllowed || isCheckingUsage || disabled)}
                                            className={cn(
                                                "h-8 w-8 rounded-md border shadow-sm flex items-center justify-center transition-all",
                                                isSearching
                                                    ? isDark
                                                        ? "bg-red-900/30 border-red-700 hover:bg-red-900/50 cursor-pointer"
                                                        : "bg-red-50 border-red-200 hover:bg-red-100 cursor-pointer"
                                                    : (hasQuery && usageAllowed && !isCheckingUsage && !disabled)
                                                        ? isDark
                                                            ? "bg-gray-800 border-border hover:bg-muted text-foreground border-gray-700"
                                                            : "bg-white border-border hover:bg-muted text-foreground"
                                                        : isDark
                                                            ? "bg-muted text-muted-foreground cursor-not-allowed"
                                                            : "bg-muted text-muted-foreground cursor-not-allowed"
                                            )}
                                            title={isSearching ? "Stop search" : canRetrySearch ? "Retry search" : "Send query"}
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
                                    {!usageAllowed && usageCheckDetails?.reason === 'usage_limit_exceeded' && (
                                        <TooltipContent className="max-w-xs">
                                            <p className={DESIGN_SYSTEM.typography.sizes.body}>
                                                {tier === 'agentic' ? 'Token' : 'Query'} limit reached. <a href="/organization/settings?tab=billing" className="underline">Upgrade your plan</a> to continue.
                                            </p>
                                        </TooltipContent>
                                    )}
                                </Tooltip>
                            </TooltipProvider>
                        </TooltipProvider>
                    </div>
                </div>
            </div>

            {/* Code Block Modal */}
            {showCodeBlock && collectionId && (
                <>
                    <div className="fixed inset-0 bg-black/60 z-40 backdrop-blur-sm" onClick={() => setShowCodeBlock(false)} />
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-8 pointer-events-none">
                        <div className="relative w-full max-w-4xl pointer-events-auto" onClick={(e) => e.stopPropagation()}>
                            <button
                                onClick={() => setShowCodeBlock(false)}
                                className={cn(
                                    "absolute top-2 right-2 z-10 h-8 w-8 rounded-md flex items-center justify-center transition-colors",
                                    isDark
                                        ? "bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground"
                                        : "bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground"
                                )}
                                title="Close (Esc)"
                            >
                                <X className="h-4 w-4" />
                            </button>
                            <ApiIntegrationDoc
                                collectionReadableId={collectionId}
                                query={query || "Ask a question about your data"}
                                tier={tier}
                                retrievalStrategy={retrievalStrategy}
                                thinking={thinking}
                                filter={toBackendFilterGroups(filterGroups)}
                                apiKey={apiKey}
                            />
                        </div>
                    </div>
                </>
            )}
        </>
    );
};
