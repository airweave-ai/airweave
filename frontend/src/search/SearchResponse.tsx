import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { Button } from '@/components/ui/button';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip';
import {
    Layers,
    TerminalSquare,
    Clock,
    Footprints,
    ClockArrowUp,
    ListStart,
    Braces,
    Copy,
    Check,
    FileJson2,
    ExternalLink
} from 'lucide-react';
import { FiMessageSquare } from 'react-icons/fi';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { JsonViewer } from '@textea/json-viewer';
import { DESIGN_SYSTEM } from '@/lib/design-system';
import { CollapsibleCard } from '@/components/ui/CollapsibleCard';
import { FiLayers, FiFilter, FiSliders, FiList, FiClock, FiGitMerge, FiType } from "react-icons/fi";
import { ChartScatter } from 'lucide-react';
import type { SearchEvent } from '@/search/types';

interface SearchResponseProps {
    searchResponse: any;
    isSearching: boolean;
    responseType?: 'raw' | 'completion';
    className?: string;
    events?: SearchEvent[];
}

export const SearchResponse: React.FC<SearchResponseProps> = ({
    searchResponse,
    isSearching,
    responseType = 'raw',
    className,
    events = []
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const [copiedCompletion, setCopiedCompletion] = useState(false);
    const [copiedJson, setCopiedJson] = useState(false);

    // Collapsible state with localStorage persistence
    const [isExpanded, setIsExpanded] = useState(() => {
        const stored = localStorage.getItem('searchResponse-expanded');
        return stored ? JSON.parse(stored) : true; // Default to expanded
    });

    // Persist state changes
    useEffect(() => {
        localStorage.setItem('searchResponse-expanded', JSON.stringify(isExpanded));
    }, [isExpanded]);

    // State for active tab - default mirrors previous behavior; will be overridden on search start
    const [activeTab, setActiveTab] = useState<'trace' | 'answer' | 'entities'>(
        responseType === 'completion' ? 'answer' : 'entities'
    );

    // State for tooltip management
    const [openTooltip, setOpenTooltip] = useState<string | null>(null);
    const tooltipTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const [hoveredTooltipContent, setHoveredTooltipContent] = useState<string | null>(null);

    // Ref for JSON viewer container for scrolling to entities
    const jsonViewerRef = useRef<HTMLDivElement>(null);

    // Extract data from response
    const searchStatus = searchResponse?.status || null;
    const statusCode = searchResponse?.error ? searchResponse.status : 200;
    const responseTime = searchResponse?.responseTime || null;
    const completion = searchResponse?.completion || '';
    const results = searchResponse?.results || [];
    const hasError = searchResponse?.error;

    // Debug logging
    useEffect(() => {
        console.log('[SearchResponseDisplay] State changed:', {
            isSearching,
            responseType,
            hasSearchResponse: !!searchResponse,
            searchResponseStatus: searchResponse?.status,
            completionLength: completion?.length,
            completionPreview: completion?.substring(0, 50) + (completion?.length > 50 ? '...' : ''),
            resultsCount: results?.length,
            searchStatus,
            hasError,
            activeTab,
            willReturnNull: !searchResponse && !isSearching
        });

        if (!searchResponse && !isSearching) {
            console.warn('[SearchResponseDisplay] Component will return NULL on next render!');
        }
    }, [isSearching, responseType, searchResponse, completion, results, searchStatus, hasError, activeTab]);

    useEffect(() => {
        if (searchStatus === 'cancelled') {
            console.log('[SearchResponseDisplay] Showing cancelled state with empty content');
        }
    }, [searchStatus]);

    // Memoize expensive style objects
    const syntaxStyle = useMemo(() => isDark ? materialOceanic : oneLight, [isDark]);

    // Create a mapping of entity IDs to source names and numbers
    const entitySourceMap = useMemo(() => {
        const map = new Map<string, { source: string; number: number }>();
        const sourceCounters = new Map<string, number>();

        // Helper function to format source names
        const formatSourceName = (name: string) => {
            return name
                .split('_')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
                .join(' ');
        };

        results.forEach((result: any) => {
            const payload = result.payload || result;
            const entityId = payload.entity_id || payload.id || payload._id;
            const rawSourceName = payload.airweave_system_metadata?.source_name || payload.source_name || 'Unknown';
            const sourceName = formatSourceName(rawSourceName);

            if (entityId) {
                // Get or create counter for this source
                let counter = sourceCounters.get(sourceName) || 0;
                counter++;
                sourceCounters.set(sourceName, counter);

                // Store the mapping
                map.set(entityId, {
                    source: sourceName,
                    number: counter
                });
            }
        });

        return map;
    }, [results]);

    // Helper functions for tooltip management with delay
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

    // Get status indicator colors
    const getStatusIndicator = useCallback((status: string | null) => {
        if (!status) return "bg-gray-400";

        switch (status) {
            case 'in_progress':
                return isDark ? "bg-blue-400" : "bg-blue-600";
            case 'success':
                return isDark ? "bg-green-400" : "bg-green-500";
            case 'no_relevant_results':
                return isDark ? "bg-amber-400" : "bg-amber-500";
            case 'cancelled':
                return isDark ? "bg-red-400" : "bg-red-500";
            default:
                return isDark ? "bg-red-400" : "bg-red-500";
        }
    }, [isDark]);

    const handleCopyCompletion = useCallback(async () => {
        await navigator.clipboard.writeText(completion);
    }, [completion]);

    const handleCopyJson = useCallback(async () => {
        await navigator.clipboard.writeText(JSON.stringify(results, null, 2));
    }, [results]);

    // Combined copy function that copies the appropriate content based on active tab
    const traceContainerRef = useRef<HTMLDivElement>(null);
    const [traceAutoScroll, setTraceAutoScroll] = useState(true);
    const handleTraceScroll = useCallback(() => {
        const el = traceContainerRef.current;
        if (!el) return;
        const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        // Re-enable auto-scroll when user is near bottom; disable when they scroll up
        setTraceAutoScroll(distanceFromBottom < 20);
    }, []);

    const handleCopy = useCallback(async () => {
        if (activeTab === 'trace') {
            const text = traceContainerRef.current?.innerText || '';
            if (text.trim()) {
                await navigator.clipboard.writeText(text.trim());
            }
            return;
        }
        if (responseType === 'completion' && activeTab === 'answer' && completion) {
            await handleCopyCompletion();
        } else if (activeTab === 'entities' && results.length > 0) {
            await handleCopyJson();
        }
    }, [activeTab, responseType, completion, results, handleCopyCompletion, handleCopyJson]);

    // Auto-scroll Trace to bottom on new events while searching, unless user scrolled up
    useEffect(() => {
        if (!isSearching) return;
        if (!traceAutoScroll) return;
        const el = traceContainerRef.current;
        if (!el) return;
        el.scrollTop = el.scrollHeight;
    }, [events?.length, isSearching, traceAutoScroll]);

    // Handle clicking on entity references in completion
    const handleEntityClick = useCallback((entityId: string) => {
        // Switch to entities tab
        setActiveTab('entities');

        // Wait for tab switch to complete, then scroll to entity
        setTimeout(() => {
            if (!jsonViewerRef.current) return;

            // Find the entity in the results array
            const entityIndex = results.findIndex((result: any) => {
                const payload = result.payload || result;
                return payload.entity_id === entityId ||
                    payload.id === entityId ||
                    payload._id === entityId;
            });

            if (entityIndex === -1) {
                console.warn(`Entity ${entityId} not found in results`);
                return;
            }

            // Try to find the DOM element for this entity in the JsonViewer
            // JsonViewer creates elements with data attributes we can query
            const container = jsonViewerRef.current;

            // Look for the entity_id field in the JSON viewer
            // We'll search for text nodes containing the entity ID
            const walker = document.createTreeWalker(
                container,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode: (node) => {
                        if (node.textContent?.includes(entityId)) {
                            return NodeFilter.FILTER_ACCEPT;
                        }
                        return NodeFilter.FILTER_SKIP;
                    }
                }
            );

            const textNode = walker.nextNode();
            if (textNode && textNode.parentElement) {
                // Scroll the element into view at the top with some context
                textNode.parentElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });

                // Highlight the element briefly
                const originalBg = textNode.parentElement.style.backgroundColor;
                textNode.parentElement.style.backgroundColor = isDark ? 'rgba(59, 130, 246, 0.3)' : 'rgba(59, 130, 246, 0.2)';
                textNode.parentElement.style.transition = 'background-color 0.3s';

                setTimeout(() => {
                    if (textNode.parentElement) {
                        textNode.parentElement.style.backgroundColor = originalBg;
                    }
                }, 2000);
            }
        }, 100);
    }, [results, isDark]);

    // (moved guard return below all hooks to satisfy hooks rules)

    // Trace helpers (ported from SearchProcess)
    const toDisplayFilter = useCallback((input: any): any => {
        const SYS_PREFIX = 'airweave_system_metadata.';
        const clone = (val: any): any => {
            if (Array.isArray(val)) return val.map(clone);
            if (val && typeof val === 'object') {
                const out: any = {};
                for (const k of Object.keys(val)) {
                    out[k] = clone(val[k]);
                }
                if (typeof out.key === 'string' && out.key.startsWith(SYS_PREFIX)) {
                    out.key = out.key.slice(SYS_PREFIX.length);
                }
                return out;
            }
            return val;
        };
        return clone(input);
    }, []);

    const JsonBlock: React.FC<{ value: string; isDark: boolean }> = ({ value, isDark }) => {
        const [copiedLocal, setCopiedLocal] = useState(false);
        const handleCopyLocal = useCallback(async () => {
            try {
                await navigator.clipboard.writeText(value);
                setCopiedLocal(true);
                setTimeout(() => setCopiedLocal(false), 1500);
            } catch {
                // noop
            }
        }, [value]);

        return (
            <div className="relative">
                <button
                    type="button"
                    onClick={handleCopyLocal}
                    title="Copy"
                    className={cn(
                        "absolute top-1 right-1 p-1 z-10",
                        DESIGN_SYSTEM.radius.button,
                        DESIGN_SYSTEM.transitions.standard,
                        isDark ? "hover:bg-gray-800 text-gray-300" : "hover:bg-gray-100 text-gray-700"
                    )}
                >
                    {copiedLocal ? <Check className={DESIGN_SYSTEM.icons.inline} /> : <Copy className={DESIGN_SYSTEM.icons.inline} />}
                </button>
                <SyntaxHighlighter
                    key={isDark ? 'json-dark' : 'json-light'}
                    language="json"
                    style={isDark ? materialOceanic : oneLight}
                    customStyle={{
                        margin: '0.25rem 0',
                        borderRadius: '0.5rem',
                        fontSize: '0.75rem',
                        padding: '0.75rem',
                        background: isDark ? 'rgba(17, 24, 39, 0.8)' : 'rgba(249, 250, 251, 0.95)'
                    }}
                >
                    {value}
                </SyntaxHighlighter>
            </div>
        );
    };

    const traceRows = useMemo(() => {
        const src = (events?.length || 0) > 500 ? events.slice(-500) : events;
        const rows: React.ReactNode[] = [];

        let inInterpretation = false;
        let interpretationHeaderShown = false;
        let interpretationData = {
            reasons: [] as string[],
            confidence: null as number | null,
            filters: [] as any[],
            refinedQuery: null as string | null,
            filterApplied: null as any
        };

        let inExpansion = false;
        let expansionHeaderShown = false;
        let expansionData = {
            strategy: null as string | null,
            reasons: [] as string[],
            alternatives: [] as string[]
        };

        let inRecency = false;
        let recencyData = {
            weight: null as number | null,
            field: null as string | null,
            oldest: null as string | null,
            newest: null as string | null,
            spanSeconds: null as number | null
        };

        let inReranking = false;
        let rerankingData = {
            reasons: [] as string[],
            rankings: [] as Array<{ index: number; relevance_score: number }>,
            k: null as number | null
        };

        let inEmbedding = false;
        let embeddingData = {
            searchMethod: null as string | null,
            neuralCount: null as number | null,
            sparseCount: null as number | null,
            dim: null as number | null,
            model: null as string | null
        };
        let pendingEmbedding: {
            searchMethod: string | null;
            neuralCount: number | null;
            sparseCount: number | null;
            dim: number | null;
            model: string | null;
        } | null = null;

        for (let i = 0; i < src.length; i++) {
            const event = src[i] as any;

            if (event.type === 'operator_start' && event.op === 'qdrant_filter') {
                let filterData = null;
                let mergeDetails: { merged?: any; existing?: any; user?: any } | null = null;
                for (let j = i + 1; j < src.length && j < i + 5; j++) {
                    if ((src[j] as any).type === 'filter_applied') {
                        filterData = (src[j] as any).filter;
                        break;
                    }
                    if ((src[j] as any).type === 'filter_merge') {
                        const e = src[j] as any;
                        mergeDetails = {
                            merged: e.merged,
                            existing: e.existing,
                            user: e.user
                        };
                    }
                    if ((src[j] as any).type === 'operator_end' && (src[j] as any).op === 'qdrant_filter') {
                        break;
                    }
                }

                rows.push(
                    <div key={`qdrant-${i}-start`} className="px-2 py-1 text-[11px] flex items-center gap-1.5">
                        <FiSliders className="h-3 w-3 opacity-80" />
                        <span className="opacity-90">Filter</span>
                        <span className={cn(
                            "ml-1 px-1 py-0 rounded text-[10px]",
                            isDark ? "bg-gray-800 text-gray-300" : "bg-gray-100 text-gray-700"
                        )}>manual</span>
                    </div>
                );

                const hasExisting = !!(mergeDetails && mergeDetails.existing && typeof mergeDetails.existing === 'object' && Object.keys(mergeDetails.existing).length > 0);
                if (hasExisting) {
                    rows.push(
                        <div key={`qdrant-${i}-merge-label`} className="px-2 py-0.5 text-[11px] opacity-70">
                            merged interpreted + manual
                        </div>
                    );
                }

                if (filterData && typeof filterData === 'object') {
                    const display = toDisplayFilter(filterData);
                    const pretty = JSON.stringify(display, null, 2);
                    rows.push(
                        <div key={`qdrant-filter-${i}`} className="py-0.5 px-2 text-[11px]">
                            <span className="opacity-90">• Filter:</span>
                            <div className="ml-3 mt-1">
                                <JsonBlock value={pretty} isDark={isDark} />
                            </div>
                        </div>
                    );
                }

                while (i < src.length && !((src[i] as any).type === 'operator_end' && (src[i] as any).op === 'qdrant_filter')) {
                    i++;
                }

                if (i < src.length) {
                    rows.push(
                        <div key={`qdrant-${i}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                            Filter applied
                        </div>
                    );

                    rows.push(
                        <div key={`qdrant-${i}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );
                }
                continue;
            }

            if (event.type === 'operator_start' && event.op === 'query_interpretation') {
                inInterpretation = true;
                interpretationData = {
                    reasons: [],
                    confidence: null,
                    filters: [],
                    refinedQuery: null,
                    filterApplied: null
                };
                if (!interpretationHeaderShown) {
                    const key = `interp-${i}`;
                    rows.push(
                        <div key={`${key}-start-immediate`} className="px-2 py-1 text-[11px] flex items-center gap-1.5">
                            <FiFilter className="h-3 w-3 opacity-80" />
                            <span className="opacity-90">Query interpretation</span>
                        </div>
                    );
                    interpretationHeaderShown = true;
                }
                continue;
            }

            if (inInterpretation) {
                if (event.type === 'interpretation_start') {
                    continue;
                }

                if (event.type === 'interpretation_reason_delta') {
                    const text = (event as any).text;
                    if (typeof text === 'string' && text.trim()) {
                        interpretationData.reasons.push(text.trim());
                    }
                    continue;
                }

                if (event.type === 'interpretation_delta') {
                    const snap = (event as any).parsed_snapshot;
                    if (snap) {
                        if (typeof snap.confidence === 'number') {
                            interpretationData.confidence = snap.confidence;
                        }
                        if (Array.isArray(snap.filters)) {
                            interpretationData.filters = snap.filters;
                        }
                        if (typeof snap.refined_query === 'string') {
                            interpretationData.refinedQuery = snap.refined_query;
                        }
                    }
                    continue;
                }

                if (event.type === 'filter_applied') {
                    interpretationData.filterApplied = (event as any).filter;
                    continue;
                }

                if (event.type === 'operator_end' && event.op === 'query_interpretation') {
                    const key = `interp-${i}`;

                    interpretationData.reasons.forEach((reason, idx) => {
                        rows.push(
                            <div key={`${key}-reason-${idx}`} className="py-0.5 px-2 text-[11px] opacity-80">
                                {reason}
                            </div>
                        );
                    });

                    if (typeof interpretationData.confidence === 'number') {
                        const applied = !!interpretationData.filterApplied;
                        rows.push(
                            <div key={`${key}-conf`} className="py-0.5 px-2 text-[11px] opacity-90">
                                {applied
                                    ? `Confidence = ${interpretationData.confidence.toFixed(2)} → Applying ${interpretationData.filters.length} filter${interpretationData.filters.length !== 1 ? 's' : ''}`
                                    : `Confidence = ${interpretationData.confidence.toFixed(2)} → Not applying filters (below threshold)`}
                            </div>
                        );
                    }

                    if (interpretationData.filterApplied && typeof interpretationData.filterApplied === 'object') {
                        const appliedDisplay = toDisplayFilter(interpretationData.filterApplied);
                        const appliedJson = JSON.stringify(appliedDisplay, null, 2);
                        rows.push(
                            <div key={`${key}-filter-applied`} className="py-0.5 px-2 text-[11px]">
                                <span className="opacity-90">Applied filter</span>
                                <div className="ml-3 mt-1">
                                    <JsonBlock value={appliedJson} isDark={isDark} />
                                </div>
                            </div>
                        );
                    } else if (interpretationData.filters.length > 0) {
                        const proposedDisplay = toDisplayFilter({ must: interpretationData.filters });
                        const filterJson = JSON.stringify(proposedDisplay, null, 2);
                        rows.push(
                            <div key={`${key}-filter-proposed`} className="py-0.5 px-2 text-[11px]">
                                <span className="opacity-90">Proposed filter (not applied)</span>
                                <div className="ml-3 mt-1">
                                    <JsonBlock value={filterJson} isDark={isDark} />
                                </div>
                            </div>
                        );
                    }

                    if (interpretationData.refinedQuery) {
                        rows.push(
                            <div key={`${key}-refined`} className="py-0.5 px-2 text-[11px] opacity-90">
                                Refined query: {interpretationData.refinedQuery}
                            </div>
                        );
                    }

                    rows.push(
                        <div key={`${key}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                            Query interpretation complete
                        </div>
                    );

                    rows.push(
                        <div key={`${key}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );

                    inInterpretation = false;
                    continue;
                }

                continue;
            }

            if (event.type === 'operator_start' && event.op === 'query_expansion') {
                inExpansion = true;
                expansionData = {
                    strategy: null,
                    reasons: [],
                    alternatives: []
                };
                if (!expansionHeaderShown) {
                    const key = `exp-${i}`;
                    rows.push(
                        <div key={`${key}-start-immediate`} className="px-2 py-1 text-[11px] flex items-center gap-1.5">
                            <FiLayers className="h-3 w-3 opacity-80" />
                            <span className="opacity-90">Query expansion</span>
                        </div>
                    );
                    expansionHeaderShown = true;
                }
                continue;
            }

            if (inExpansion) {
                if (event.type === 'expansion_start') {
                    const strategy = (event as any).strategy;
                    if (strategy) {
                        expansionData.strategy = String(strategy).toUpperCase();
                    }
                    continue;
                }
                if (event.type === 'expansion_reason_delta') {
                    const text = (event as any).text;
                    if (typeof text === 'string' && text.trim()) {
                        expansionData.reasons.push(text.trim());
                    }
                    continue;
                }
                if (event.type === 'expansion_delta') {
                    const alts = (event as any).alternatives_snapshot;
                    if (Array.isArray(alts)) {
                        expansionData.alternatives = alts;
                    }
                    continue;
                }
                if (event.type === 'expansion_done') {
                    const alts = (event as any).alternatives;
                    if (Array.isArray(alts)) {
                        expansionData.alternatives = alts;
                    }
                }
                if (event.type === 'operator_end' && event.op === 'query_expansion') {
                    const key = `exp-${i}`;
                    if (expansionData.strategy) {
                        rows.push(
                            <div key={`${key}-strategy`} className="py-0.5 px-2 text-[11px] opacity-80">
                                Strategy: {expansionData.strategy}
                            </div>
                        );
                    }
                    expansionData.reasons.forEach((reason, idx) => {
                        rows.push(
                            <div key={`${key}-reason-${idx}`} className="py-0.5 px-2 text-[11px] opacity-80">
                                {reason}
                            </div>
                        );
                    });
                    if (expansionData.alternatives.length > 0) {
                        rows.push(
                            <div key={`${key}-alts-header`} className="py-0.5 px-2 text-[11px] opacity-90">
                                Generated {expansionData.alternatives.length} alternative{expansionData.alternatives.length !== 1 ? 's' : ''}:
                            </div>
                        );
                        expansionData.alternatives.forEach((alt, idx) => {
                            rows.push(
                                <div key={`${key}-alt-${idx}`} className="py-0.5 px-2 pl-4 text-[11px] opacity-80">
                                    {idx + 1}. {alt}
                                </div>
                            );
                        });
                    }
                    rows.push(
                        <div key={`${key}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                            Query expansion complete
                        </div>
                    );
                    rows.push(
                        <div key={`${key}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );
                    inExpansion = false;
                    continue;
                }
                continue;
            }

            if (event.type === 'operator_start' && event.op === 'embedding') {
                inEmbedding = true;
                embeddingData = {
                    searchMethod: null,
                    neuralCount: null,
                    sparseCount: null,
                    dim: null,
                    model: null
                };
                continue;
            }
            if (inEmbedding) {
                if (event.type === 'embedding_start') {
                    const method = (event as any).search_method;
                    if (method) {
                        embeddingData.searchMethod = String(method).toLowerCase();
                    }
                    continue;
                }
                if (event.type === 'embedding_done') {
                    const e = event as any;
                    embeddingData.neuralCount = e.neural_count;
                    embeddingData.sparseCount = e.sparse_count;
                    embeddingData.dim = e.dim;
                    embeddingData.model = e.model;
                }
                if (event.type === 'embedding_fallback') {
                    const reason = (event as any).reason;
                    rows.push(
                        <div key={`embed-fallback-${i}`} className="py-0.5 px-2 text-[11px] opacity-90">
                            • Embedding fallback: {reason}
                        </div>
                    );
                    inEmbedding = false;
                    continue;
                }
                if (event.type === 'operator_end' && event.op === 'embedding') {
                    pendingEmbedding = { ...embeddingData };
                    inEmbedding = false;
                    continue;
                }
                continue;
            }

            if (event.type === 'operator_start' && event.op === 'vector_search') {
                const vectorSearchData = {
                    method: null as string | null,
                    finalCount: null as number | null,
                    topScores: [] as number[]
                };
                let j = i + 1;
                while (j < src.length && (src[j] as any).type !== 'operator_end') {
                    const nextEvent = src[j] as any;
                    if (nextEvent.type === 'vector_search_start') {
                        vectorSearchData.method = nextEvent.method;
                    } else if (nextEvent.type === 'vector_search_done') {
                        vectorSearchData.finalCount = nextEvent.final_count;
                        vectorSearchData.topScores = nextEvent.top_scores || [];
                    }
                    j++;
                }

                const key = `vector-${i}`;
                const vMethod = (vectorSearchData.method || 'hybrid') as 'hybrid' | 'neural' | 'keyword';
                const VIcon = vMethod === 'hybrid' ? FiGitMerge : vMethod === 'neural' ? ChartScatter : FiType;

                rows.push(
                    <div key={`${key}-start`} className="px-2 py-1 text-[11px] flex items-center gap-1.5">
                        <VIcon className="h-3 w-3 opacity-80" />
                        <span className="opacity-90">Retrieval</span>
                        <span className={cn(
                            "ml-1 px-1 py-0 rounded text-[10px]",
                            isDark ? "bg-gray-800 text-gray-300" : "bg-gray-100 text-gray-700"
                        )}>{vMethod}</span>
                    </div>
                );

                if (pendingEmbedding) {
                    if (pendingEmbedding.neuralCount && pendingEmbedding.neuralCount > 0) {
                        rows.push(
                            <div key={`${key}-embed-neural`} className="py-0.5 px-2 text-[11px] opacity-80">
                                Embeddings: {pendingEmbedding.neuralCount} neural{pendingEmbedding.neuralCount !== 1 ? 's' : ''} (dim {pendingEmbedding.dim || 'unknown'})
                            </div>
                        );
                    }
                    if (pendingEmbedding.sparseCount && pendingEmbedding.sparseCount > 0) {
                        rows.push(
                            <div key={`${key}-embed-sparse`} className="py-0.5 px-2 text-[11px] opacity-80">
                                Embeddings: {pendingEmbedding.sparseCount} sparse (BM25)
                            </div>
                        );
                    }
                }

                if (vectorSearchData.finalCount !== null) {
                    rows.push(
                        <div key={`${key}-found`} className="py-0.5 px-2 text-[11px] opacity-80">
                            Retrieved {vectorSearchData.finalCount} candidate result{vectorSearchData.finalCount !== 1 ? 's' : ''}
                        </div>
                    );
                }

                rows.push(
                    <div key={`${key}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                        Retrieval complete
                    </div>
                );
                rows.push(
                    <div key={`${key}-separator`} className="py-1">
                        <div className="mx-2 border-t border-border/30"></div>
                    </div>
                );
                pendingEmbedding = null;
                while (i < src.length && !((src[i] as any).type === 'operator_end' && (src[i] as any).op === 'vector_search')) {
                    i++;
                }
                continue;
            }

            if (event.type === 'operator_start' && event.op === 'recency') {
                inRecency = true;
                recencyData = {
                    weight: null,
                    field: null,
                    oldest: null,
                    newest: null,
                    spanSeconds: null
                };
                continue;
            }
            if (inRecency) {
                if (event.type === 'recency_start') {
                    const weight = (event as any).requested_weight;
                    if (typeof weight === 'number') {
                        recencyData.weight = weight;
                    }
                    continue;
                }
                if (event.type === 'recency_span') {
                    const e = event as any;
                    recencyData.field = e.field;
                    recencyData.oldest = e.oldest;
                    recencyData.newest = e.newest;
                    recencyData.spanSeconds = e.span_seconds;
                    continue;
                }
                if (event.type === 'recency_skipped') {
                    const reason = (event as any).reason;
                    rows.push(
                        <div key={`recency-skip-${i}`} className="py-0.5 px-2 text-[11px] opacity-90">
                            • Recency bias skipped: {reason}
                        </div>
                    );
                    rows.push(
                        <div key={`recency-skip-${i}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );
                    while (i < src.length && !((src[i] as any).type === 'operator_end' && (src[i] as any).op === 'recency')) {
                        i++;
                    }
                    inRecency = false;
                    continue;
                }
                if (event.type === 'operator_end' && event.op === 'recency') {
                    const key = `recency-${i}`;
                    const formatTimeSpan = (seconds: number | null) => {
                        if (!seconds) return 'unknown';
                        const days = Math.floor(seconds / 86400);
                        const hours = Math.floor((seconds % 86400) / 3600);
                        const minutes = Math.floor((seconds % 3600) / 60);
                        const parts = [] as string[];
                        if (days > 0) parts.push(`${days} day${days !== 1 ? 's' : ''}`);
                        if (hours > 0) parts.push(`${hours} hour${hours !== 1 ? 's' : ''}`);
                        if (minutes > 0 && days === 0) parts.push(`${minutes} minute${minutes !== 1 ? 's' : ''}`);
                        return parts.length > 0 ? parts.join(', ') : 'less than a minute';
                    };
                    const formatDate = (dateStr: string | null) => {
                        if (!dateStr) return 'unknown';
                        try {
                            const date = new Date(dateStr);
                            return date.toLocaleDateString('en-US', {
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit'
                            });
                        } catch {
                            return dateStr;
                        }
                    };
                    rows.push(
                        <div key={`${key}-start`} className="px-2 py-1 text-[11px] flex items-center gap-1.5">
                            <ClockArrowUp className="h-3 w-3 opacity-80" />
                            <span className="opacity-90">Recency bias</span>
                            {recencyData.weight !== null && (
                                <span className={cn(
                                    "ml-1 px-1 py-0 rounded text-[10px]",
                                    isDark ? "bg-gray-800 text-gray-300" : "bg-gray-100 text-gray-700"
                                )}>{recencyData.weight}</span>
                            )}
                        </div>
                    );
                    if (recencyData.oldest) {
                        rows.push(
                            <div key={`${key}-oldest`} className="py-0.5 px-2 text-[11px] opacity-80">
                                Oldest data point: {formatDate(recencyData.oldest)}
                            </div>
                        );
                    }
                    if (recencyData.newest) {
                        rows.push(
                            <div key={`${key}-newest`} className="py-0.5 px-2 text-[11px] opacity-80">
                                Newest data point: {formatDate(recencyData.newest)}
                            </div>
                        );
                    }
                    if (recencyData.spanSeconds !== null) {
                        rows.push(
                            <div key={`${key}-span`} className="py-0.5 px-2 text-[11px] opacity-80">
                                Time span: {formatTimeSpan(recencyData.spanSeconds)}
                            </div>
                        );
                    }
                    rows.push(
                        <div key={`${key}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                            Recency bias applied
                        </div>
                    );
                    rows.push(
                        <div key={`${key}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );
                    inRecency = false;
                    continue;
                }
                continue;
            }

            if (event.type === 'operator_start' && event.op === 'llm_reranking') {
                inReranking = true;
                rerankingData = { reasons: [], rankings: [], k: null };
                rows.push(
                    <div key={`rerank-${i}-start`} className="px-2 py-1 text-[11px] flex items-center gap-1.5">
                        <ListStart className="h-3 w-3 opacity-80" />
                        <span className="opacity-90">AI reranking</span>
                    </div>
                );
                continue;
            }
            if (inReranking) {
                if (event.type === 'reranking_start') {
                    const k = (event as any).k;
                    if (typeof k === 'number') {
                        rerankingData.k = k;
                        rows.push(
                            <div key={`rerank-${i}-start-updated`} className="py-0.5 px-2 text-[11px] opacity-90">
                                Reranking top {k} results
                            </div>
                        );
                    }
                    continue;
                }
                if (event.type === 'reranking_reason_delta') {
                    const text = (event as any).text;
                    if (typeof text === 'string' && text.trim()) {
                        rerankingData.reasons.push(text.trim());
                        rows.push(
                            <div key={`rerank-${i}-reason-${rerankingData.reasons.length}`} className="py-0.5 px-2 text-[11px] opacity-80">
                                {text.trim()}
                            </div>
                        );
                    }
                    continue;
                }
                if (event.type === 'reranking_delta') {
                    const rankings = (event as any).rankings_snapshot;
                    if (Array.isArray(rankings)) {
                        rerankingData.rankings = rankings;
                    }
                    continue;
                }
                if (event.type === 'reranking_done') {
                    const rankings = (event as any).rankings;
                    if (Array.isArray(rankings)) {
                        rerankingData.rankings = rankings;
                    }
                }
                if (event.type === 'operator_end' && event.op === 'llm_reranking') {
                    const key = `rerank-${i}`;
                    if (rerankingData.rankings.length > 0) {
                        rows.push(
                            <div key={`${key}-rankings-header`} className="py-0.5 px-2 text-[11px] opacity-90">
                                Reranked {rerankingData.rankings.length} result{rerankingData.rankings.length !== 1 ? 's' : ''}:
                            </div>
                        );
                        const topRankings = rerankingData.rankings.slice(0, 5);
                        topRankings.forEach((ranking, idx) => {
                            const score = typeof ranking.relevance_score === 'number' ? ranking.relevance_score.toFixed(2) : 'N/A';
                            rows.push(
                                <div key={`${key}-rank-${idx}`} className="py-0.5 px-2 pl-4 text-[11px] opacity-80">
                                    #{idx + 1}: Result {ranking.index} (relevance: {score})
                                </div>
                            );
                        });
                        if (rerankingData.rankings.length > 5) {
                            rows.push(
                                <div key={`${key}-more`} className="py-0.5 px-2 pl-4 text-[11px] opacity-60">
                                    ... and {rerankingData.rankings.length - 5} more
                                </div>
                            );
                        }
                    }
                    rows.push(
                        <div key={`${key}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                            Reranking complete
                        </div>
                    );
                    rows.push(
                        <div key={`${key}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );
                    inReranking = false;
                    continue;
                }
                continue;
            }

            if (event.type === 'completion_start' || event.type === 'completion_delta' || event.type === 'completion_done') {
                continue;
            }
            if (event.type === 'operator_start' && event.op === 'completion') {
                continue;
            }
            if (event.type === 'operator_end' && event.op === 'completion') {
                continue;
            }

            if (event.type === 'connected') {
                rows.push(
                    <div key={(event.seq ?? i) + "-" + i} className="py-0.5 px-2 text-[11px] opacity-90">
                        Connected
                    </div>
                );
            } else if (event.type === 'start') {
                rows.push(
                    <div key={(event.seq ?? i) + "-" + i} className="py-0.5 px-2 text-[11px] opacity-90">
                        Starting search
                    </div>
                );
                rows.push(
                    <div key={`${(event.seq ?? i)}-separator`} className="py-1">
                        <div className="mx-2 border-t border-border/30"></div>
                    </div>
                );
            } else if (event.type === 'done') {
                rows.push(
                    <div key={(event.seq ?? i) + "-" + i} className="py-0.5 px-2 text-[11px] opacity-90 flex items-center gap-1.5">
                        <Check className="h-3 w-3 opacity-80" strokeWidth={1.5} />
                        Search complete
                    </div>
                );
            } else if (event.type === 'results' || event.type === 'summary') {
                continue;
            } else if (event.type === 'error') {
                const e = event as any;
                rows.push(
                    <div key={(event.seq ?? i) + "-" + i} className="py-0.5 px-2 text-[11px] text-red-400">
                        Error{e.operation ? ` in ${e.operation}` : ''}: {e.message}
                    </div>
                );
            } else {
                continue;
            }
        }

        if (inInterpretation && (interpretationData.reasons.length > 0)) {
            const key = `interp-incomplete`;
            rows.push(
                <div key={`${key}-start`} className="py-0.5 px-2 text-[11px] opacity-90">
                    • starting query interpretation
                </div>
            );
            interpretationData.reasons.forEach((reason, idx) => {
                rows.push(
                    <div key={`${key}-reason-${idx}`} className="py-0.5 px-2 text-[11px] opacity-80">
                        • {reason}
                    </div>
                );
            });
        }

        if (inExpansion && (expansionData.reasons.length > 0 || expansionData.strategy || expansionData.alternatives.length > 0)) {
            const key = `exp-incomplete`;
            rows.push(
                <div key={`${key}-start`} className="py-0.5 px-2 text-[11px] opacity-90">
                    • Starting query expansion{expansionData.strategy ? ` with strategy '${expansionData.strategy}'` : ''}
                </div>
            );
            expansionData.reasons.forEach((reason, idx) => {
                rows.push(
                    <div key={`${key}-reason-${idx}`} className="py-0.5 px-2 text-[11px] opacity-80">
                        • {reason}
                    </div>
                );
            });
            if (expansionData.alternatives.length > 0) {
                rows.push(
                    <div key={`${key}-alts-header`} className="py-0.5 px-2 text-[11px] opacity-90">
                        • Generated {expansionData.alternatives.length} alternative{expansionData.alternatives.length !== 1 ? 's' : ''}:
                    </div>
                );
                expansionData.alternatives.forEach((alt, idx) => {
                    rows.push(
                        <div key={`${key}-alt-${idx}`} className="py-0.5 px-2 pl-4 text-[11px] opacity-80">
                            {idx + 1}. {alt}
                        </div>
                    );
                });
            }
        }

        return rows;
    }, [events, isDark, toDisplayFilter]);

    // Tab switching effects
    useEffect(() => {
        if (searchStatus === 'cancelled') return;
        if (isSearching) {
            setActiveTab('trace');
        }
    }, [isSearching, searchStatus]);

    useEffect(() => {
        if (searchStatus === 'cancelled') return;
        if (responseType === 'completion' && isSearching && completion && completion.length > 0) {
            if (activeTab === 'trace') setActiveTab('answer');
        }
    }, [responseType, isSearching, completion, activeTab, searchStatus]);

    useEffect(() => {
        if (searchStatus === 'cancelled') return;
        if (responseType === 'raw' && !isSearching && Array.isArray(results) && results.length > 0 && searchStatus === 'success') {
            setActiveTab('entities');
        }
    }, [responseType, isSearching, results, searchStatus]);

    // Guard: show nothing if no response and not loading (after hooks per lint rules)
    if (!searchResponse && !isSearching) {
        return null;
    }

    // Create header content with status information
    const headerContent = (
        <>
            <span className={cn(DESIGN_SYSTEM.typography.sizes.label, "opacity-80")}>Response</span>
            <div className="flex items-center gap-3">
                {searchStatus && !hasError && (
                    <div className="flex items-center">
                        <div className={cn(
                            "h-1.5 w-1.5 rounded-full mr-1",
                            getStatusIndicator(searchStatus)
                        )}></div>
                        <span className={cn(DESIGN_SYSTEM.typography.sizes.label, "opacity-80")}>
                            {searchStatus.replace(/_/g, ' ')}
                        </span>
                    </div>
                )}

                {hasError && (
                    <div className="flex items-center text-red-500">
                        <span className={DESIGN_SYSTEM.typography.sizes.body}>Error</span>
                    </div>
                )}
            </div>

            <div className="flex items-center gap-2.5">
                {statusCode && (
                    <div className={cn("flex items-center opacity-80", DESIGN_SYSTEM.typography.sizes.label)}>
                        <TerminalSquare className={cn(DESIGN_SYSTEM.icons.inline, "mr-1")} strokeWidth={1.5} />
                        <span className="font-mono">HTTP {statusCode}</span>
                    </div>
                )}

                {responseTime && (
                    <div className={cn("flex items-center opacity-80", DESIGN_SYSTEM.typography.sizes.label)}>
                        <Clock className={cn(DESIGN_SYSTEM.icons.inline, "mr-1")} strokeWidth={1.5} />
                        <span className="font-mono">{responseTime}ms</span>
                    </div>
                )}
            </div>
        </>
    );

    // Create status ribbon
    const statusRibbon = (
        <div className="h-1.5 w-full relative overflow-hidden">
            {isSearching ? (
                <>
                    <div className={cn(
                        "absolute inset-0 h-1.5 bg-gradient-to-r from-blue-500 to-indigo-500"
                    )}></div>
                    <div className={cn(
                        "absolute inset-0 h-1.5 bg-gradient-to-r from-transparent via-white/30 to-transparent",
                        "animate-pulse"
                    )}></div>
                </>
            ) : (
                <div className={cn(
                    "absolute inset-0 h-1.5 bg-gradient-to-r",
                    hasError
                        ? "from-red-500 to-red-600"
                        : searchStatus === 'in_progress'
                            ? "from-blue-500 to-indigo-500"
                            : searchStatus === 'success'
                                ? "from-green-500 to-emerald-500"
                                : searchStatus === 'no_relevant_results'
                                    ? "from-amber-400 to-amber-500"
                                    : searchStatus === 'cancelled'
                                        ? "from-red-500 to-red-600"
                                        : "from-gray-400 to-gray-500"
                )}></div>
            )}
        </div>
    );

    return (
        <CollapsibleCard
            header={headerContent}
            statusRibbon={statusRibbon}
            isExpanded={isExpanded}
            onToggle={setIsExpanded}
            onCopy={handleCopy}
            copyTooltip={activeTab === 'trace' ? "Copy trace" : activeTab === 'answer' ? "Copy answer" : "Copy entities"}
            autoExpandOnSearch={isSearching}
            className={className}
        >
            {/* Content Section with Tabs */}
            <div className="flex flex-col">
                {/* Error Display */}
                {hasError && (
                    <div className={cn(
                        "border-t p-4",
                        isDark ? "border-gray-800/50 bg-red-950/20" : "border-gray-200/50 bg-red-50"
                    )}>
                        <div className={cn(
                            "text-sm",
                            isDark ? "text-red-300" : "text-red-700"
                        )}>
                            {searchResponse.error}
                        </div>
                    </div>
                )}

                {/* Tab Navigation */}
                {!hasError && (
                    <TooltipProvider>
                        <div className={cn(
                            "flex items-center border-t",
                            isDark ? "border-gray-800/50 bg-gray-900/70" : "border-gray-200/50 bg-gray-50"
                        )}>
                            {/* Trace tab (left) */}
                            <button
                                onClick={() => setActiveTab('trace')}
                                className={cn(
                                    "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                    activeTab === 'trace'
                                        ? isDark
                                            ? "text-white bg-gray-800/70"
                                            : "text-gray-900 bg-white"
                                        : isDark
                                            ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30"
                                            : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                                )}
                            >
                                <div className="flex items-center gap-1.5">
                                    <Footprints className="h-3 w-3" />
                                    Trace
                                </div>
                                {activeTab === 'trace' && (
                                    <div className={cn(
                                        "absolute bottom-0 left-0 right-0 h-0.5",
                                        isDark ? "bg-blue-400" : "bg-blue-600"
                                    )} />
                                )}
                            </button>
                            {/* Middle + Right depend on responseType */}
                            {responseType === 'raw' ? (
                                <>
                                    {/* Entities (middle) */}
                                    <button
                                        onClick={() => setActiveTab('entities')}
                                        className={cn(
                                            "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                            activeTab === 'entities'
                                                ? isDark
                                                    ? "text-white bg-gray-800/70"
                                                    : "text-gray-900 bg-white"
                                                : isDark
                                                    ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30"
                                                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                                        )}
                                    >
                                        <div className="flex items-center gap-1.5">
                                            <FileJson2 className="h-3 w-3" strokeWidth={1.5} />
                                            Entities
                                        </div>
                                        {activeTab === 'entities' && (
                                            <div className={cn(
                                                "absolute bottom-0 left-0 right-0 h-0.5",
                                                isDark ? "bg-blue-400" : "bg-blue-600"
                                            )} />
                                        )}
                                    </button>

                                    {/* Answer (right, disabled) */}
                                    <Tooltip open={openTooltip === "answerTab"}>
                                        <TooltipTrigger asChild>
                                            <button
                                                onMouseEnter={() => handleTooltipMouseEnter("answerTab")}
                                                onMouseLeave={() => handleTooltipMouseLeave("answerTab")}
                                                className={cn(
                                                    "px-3.5 py-2 text-[13px] font-medium transition-colors relative cursor-not-allowed",
                                                    isDark
                                                        ? "text-gray-600 bg-gray-900/30"
                                                        : "text-gray-400 bg-gray-50/50"
                                                )}
                                            >
                                                <div className="flex items-center gap-1.5 opacity-60">
                                                    <FiMessageSquare className="h-3 w-3" />
                                                    Answer
                                                </div>
                                            </button>
                                        </TooltipTrigger>
                                        <TooltipContent
                                            side="top"
                                            sideOffset={2}
                                            className={cn(
                                                "max-w-[240px] p-2.5 rounded-md bg-gray-900 text-white",
                                                "border border-white/10 shadow-xl"
                                            )}
                                            arrowClassName="fill-gray-900"
                                            onMouseEnter={() => handleTooltipContentMouseEnter("answerTab")}
                                            onMouseLeave={() => handleTooltipContentMouseLeave("answerTab")}
                                        >
                                            <div className="flex items-start gap-1.5">
                                                <FiMessageSquare className="h-3.5 w-3.5 mt-0.5 flex-shrink-0 text-white/80" />
                                                <p className="text-xs text-white/90 leading-relaxed">
                                                    To get an answer to your question, turn on "Generate answer" when searching.
                                                </p>
                                            </div>
                                        </TooltipContent>
                                    </Tooltip>
                                </>
                            ) : (
                                <>
                                    {/* Answer (middle) */}
                                    <button
                                        onClick={() => setActiveTab('answer')}
                                        className={cn(
                                            "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                            activeTab === 'answer'
                                                ? isDark
                                                    ? "text-white bg-gray-800/70"
                                                    : "text-gray-900 bg-white"
                                                : isDark
                                                    ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30"
                                                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                                        )}
                                    >
                                        <div className="flex items-center gap-1.5">
                                            <FiMessageSquare className="h-3 w-3" />
                                            Answer
                                        </div>
                                        {activeTab === 'answer' && (
                                            <div className={cn(
                                                "absolute bottom-0 left-0 right-0 h-0.5",
                                                isDark ? "bg-blue-400" : "bg-blue-600"
                                            )} />
                                        )}
                                    </button>

                                    {/* Entities (right) */}
                                    <button
                                        onClick={() => setActiveTab('entities')}
                                        className={cn(
                                            "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                            activeTab === 'entities'
                                                ? isDark
                                                    ? "text-white bg-gray-800/70"
                                                    : "text-gray-900 bg-white"
                                                : isDark
                                                    ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30"
                                                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                                        )}
                                    >
                                        <div className="flex items-center gap-1.5">
                                            <FileJson2 className="h-3 w-3" strokeWidth={1.5} />
                                            Entities
                                        </div>
                                        {activeTab === 'entities' && (
                                            <div className={cn(
                                                "absolute bottom-0 left-0 right-0 h-0.5",
                                                isDark ? "bg-blue-400" : "bg-blue-600"
                                            )} />
                                        )}
                                    </button>
                                </>
                            )}
                        </div>
                    </TooltipProvider>
                )}

                {/* Tab Content */}
                {!hasError && (
                    <div className={cn(
                        "border-t relative",
                        isDark ? "border-gray-800/50" : "border-gray-200/50"
                    )}>
                        {/* Trace Tab Content */}
                        <div style={{ display: activeTab === 'trace' ? 'block' : 'none' }}>
                            <div ref={traceContainerRef} onScroll={handleTraceScroll} className={cn(
                                "overflow-auto max-h-[438px]",
                                DESIGN_SYSTEM.spacing.padding.compact,
                                isDark ? "bg-gray-950" : "bg-white"
                            )}>
                                {(!events || events.length === 0) ? (
                                    <div className="px-1 py-1">
                                        <div className="space-y-2 animate-pulse">
                                            <div className={cn("h-3 rounded", isDark ? "bg-gray-800" : "bg-gray-200")}></div>
                                            <div className={cn("h-3 rounded", isDark ? "bg-gray-800" : "bg-gray-200")}></div>
                                            <div className={cn("h-3 rounded w-5/6", isDark ? "bg-gray-800" : "bg-gray-200")}></div>
                                            <div className="py-1">
                                                <div className={cn("h-px", isDark ? "bg-gray-800" : "bg-gray-200")}></div>
                                            </div>
                                            <div className={cn("h-3 rounded", isDark ? "bg-gray-800" : "bg-gray-200")}></div>
                                            <div className={cn("h-3 rounded w-2/3", isDark ? "bg-gray-800" : "bg-gray-200")}></div>
                                            <div className={cn("h-3 rounded w-1/2", isDark ? "bg-gray-800" : "bg-gray-200")}></div>
                                        </div>
                                    </div>
                                ) : (
                                    <>
                                        {traceRows}
                                        {events.some((e: any) => e?.type === 'cancelled') && (
                                            <div className="py-0.5 px-2 text-[11px] text-red-500">
                                                Search cancelled
                                            </div>
                                        )}
                                        {isSearching && (
                                            <div className="py-0.5 px-2 text-[11px] opacity-70 flex items-center gap-2">
                                                <span>Searching</span>
                                                <span className="flex items-center gap-1">
                                                    <span className={cn(
                                                        "h-1 w-1 rounded-full animate-pulse",
                                                        isDark ? "bg-gray-600" : "bg-gray-400"
                                                    )} style={{ animationDelay: '0ms' }} />
                                                    <span className={cn(
                                                        "h-1 w-1 rounded-full animate-pulse",
                                                        isDark ? "bg-gray-600" : "bg-gray-400"
                                                    )} style={{ animationDelay: '150ms' }} />
                                                    <span className={cn(
                                                        "h-1 w-1 rounded-full animate-pulse",
                                                        isDark ? "bg-gray-600" : "bg-gray-400"
                                                    )} style={{ animationDelay: '300ms' }} />
                                                </span>
                                            </div>
                                        )}
                                    </>
                                )}
                            </div>
                        </div>

                        {/* Answer Tab Content - Always rendered but hidden when not active */}
                        {responseType === 'completion' && (completion || isSearching) && (
                            <div style={{ display: activeTab === 'answer' ? 'block' : 'none' }}>


                                <div className={cn(
                                    "overflow-auto max-h-[438px] leading-relaxed",
                                    DESIGN_SYSTEM.spacing.padding.compact,
                                    DESIGN_SYSTEM.typography.sizes.body,
                                    isDark ? "bg-gray-900 text-gray-200" : "bg-white text-gray-800"
                                )}>
                                    {(() => {
                                        const showingSkeleton = isSearching && !completion;
                                        const showingCompletion = !!completion;
                                        const showingCursor = isSearching && completion;

                                        console.log('[SearchResponseDisplay] Completion rendering logic:', {
                                            isSearching,
                                            hasCompletion: !!completion,
                                            completionLength: completion?.length,
                                            showingSkeleton,
                                            showingCompletion,
                                            showingCursor,
                                            completionSource: isSearching ? 'STREAMING' : 'FINAL'
                                        });

                                        return null; // This return is just for the IIFE
                                    })()}
                                    {isSearching && !completion ? (
                                        // Show skeleton only if we're searching but have no completion yet
                                        <div className="animate-pulse h-32 w-full">
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-5/6 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-2/3 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
                                        </div>
                                    ) : completion ? (
                                        // Show the actual completion (streaming or final)
                                        <ReactMarkdown
                                            remarkPlugins={[remarkGfm]}
                                            components={{
                                                h1: ({ node, ...props }) => <h1 className="text-[13px] font-semibold mt-0 mb-1.5" {...props} />,
                                                h2: ({ node, ...props }) => <h2 className="text-[12px] font-semibold mt-0 mb-1.5" {...props} />,
                                                h3: ({ node, ...props }) => <h3 className="text-[12px] font-medium mt-0 mb-1.5" {...props} />,
                                                ul: ({ node, ...props }) => <ul className="list-disc pl-4 mt-0 mb-1 space-y-0.5" {...props} />,
                                                ol: ({ node, ...props }) => <ol className="list-decimal pl-4 mt-0 mb-1 space-y-0.5" {...props} />,
                                                table: ({ node, ...props }) => (
                                                    <div className="overflow-x-auto my-4">
                                                        <table className={cn(
                                                            "min-w-full divide-y",
                                                            isDark ? "divide-gray-700" : "divide-gray-200"
                                                        )} {...props} />
                                                    </div>
                                                ),
                                                thead: ({ node, ...props }) => (
                                                    <thead className={cn(
                                                        isDark ? "bg-gray-800/50" : "bg-gray-50"
                                                    )} {...props} />
                                                ),
                                                tbody: ({ node, ...props }) => (
                                                    <tbody className={cn(
                                                        "divide-y",
                                                        isDark ? "divide-gray-800 bg-gray-900/30" : "divide-gray-200 bg-white"
                                                    )} {...props} />
                                                ),
                                                tr: ({ node, ...props }) => (
                                                    <tr className={cn(
                                                        "transition-colors",
                                                        isDark ? "hover:bg-gray-800/30" : "hover:bg-gray-50"
                                                    )} {...props} />
                                                ),
                                                th: ({ node, ...props }) => (
                                                    <th className={cn(
                                                        "px-3 py-1.5 text-left text-[11px] font-medium uppercase tracking-wider",
                                                        isDark ? "text-gray-300" : "text-gray-700"
                                                    )} {...props} />
                                                ),
                                                td: ({ node, ...props }) => (
                                                    <td className={cn(
                                                        "px-3 py-1.5 text-[12px]",
                                                        isDark ? "text-gray-300" : "text-gray-700"
                                                    )} {...props} />
                                                ),
                                                li: ({ children, ...props }) => {
                                                    // Process list item content to replace [[entity_id]] with clickable links
                                                    const processedChildren = React.Children.map(children, (child) => {
                                                        if (typeof child === 'string') {
                                                            // Split by entity reference pattern [[entity_id]]
                                                            const parts = child.split(/(\[\[[^\]]+\]\])/g);
                                                            return parts.map((part, index) => {
                                                                const match = part.match(/^\[\[([^\]]+)\]\]$/);
                                                                if (match) {
                                                                    const entityId = match[1];
                                                                    const sourceInfo = entitySourceMap.get(entityId);
                                                                    const displayText = sourceInfo
                                                                        ? `${sourceInfo.source} [${sourceInfo.number}]`
                                                                        : entityId;

                                                                    return (
                                                                        <button
                                                                            key={index}
                                                                            onClick={() => handleEntityClick(entityId)}
                                                                            className={cn(
                                                                                "inline-flex items-center gap-0.5 px-1 py-0.5 rounded-md text-[11px] font-medium",
                                                                                "transition-colors cursor-pointer",
                                                                                isDark
                                                                                    ? "bg-blue-950/50 text-blue-300 hover:bg-blue-900/70 hover:text-blue-200"
                                                                                    : "bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700",
                                                                                "border",
                                                                                isDark ? "border-blue-800/50" : "border-blue-200"
                                                                            )}
                                                                            title={`View in Entities tab`}
                                                                        >
                                                                            {displayText}
                                                                        </button>
                                                                    );
                                                                }
                                                                return part;
                                                            });
                                                        }
                                                        return child;
                                                    });
                                                    return <li className="my-0.5" {...props}>{processedChildren}</li>;
                                                },
                                                p: ({ children, ...props }) => {
                                                    // Process paragraph content to replace [[entity_id]] with clickable links
                                                    const processedChildren = React.Children.map(children, (child) => {
                                                        if (typeof child === 'string') {
                                                            // Split by entity reference pattern [[entity_id]]
                                                            const parts = child.split(/(\[\[[^\]]+\]\])/g);
                                                            return parts.map((part, index) => {
                                                                const match = part.match(/^\[\[([^\]]+)\]\]$/);
                                                                if (match) {
                                                                    const entityId = match[1];
                                                                    const sourceInfo = entitySourceMap.get(entityId);
                                                                    const displayText = sourceInfo
                                                                        ? `${sourceInfo.source} [${sourceInfo.number}]`
                                                                        : entityId;

                                                                    return (
                                                                        <button
                                                                            key={index}
                                                                            onClick={() => handleEntityClick(entityId)}
                                                                            className={cn(
                                                                                "inline-flex items-center gap-0.5 px-1 py-0.5 rounded-md text-[11px] font-medium",
                                                                                "transition-colors cursor-pointer",
                                                                                isDark
                                                                                    ? "bg-blue-950/50 text-blue-300 hover:bg-blue-900/70 hover:text-blue-200"
                                                                                    : "bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700",
                                                                                "border",
                                                                                isDark ? "border-blue-800/50" : "border-blue-200"
                                                                            )}
                                                                            title={`View in Entities tab`}
                                                                        >
                                                                            {displayText}
                                                                        </button>
                                                                    );
                                                                }
                                                                return part;
                                                            });
                                                        }
                                                        return child;
                                                    });
                                                    return <p className="mt-0 mb-1 leading-relaxed" {...props}>{processedChildren}</p>;
                                                },
                                                blockquote: ({ node, ...props }) => (
                                                    <blockquote className={cn(
                                                        "border-l-4 pl-4 my-3 italic",
                                                        isDark ? "border-gray-600 text-gray-300" : "border-gray-300 text-gray-700"
                                                    )} {...props} />
                                                ),
                                                hr: ({ node, ...props }) => (
                                                    <hr className={cn(
                                                        "my-2",
                                                        isDark ? "border-gray-700" : "border-gray-300"
                                                    )} {...props} />
                                                ),
                                                strong: ({ node, ...props }) => <strong className="font-semibold" {...props} />,
                                                em: ({ node, ...props }) => <em className="italic" {...props} />,
                                                code(props) {
                                                    const { children, className, node, ...rest } = props;
                                                    const match = /language-(\w+)/.exec(className || '');
                                                    return match ? (
                                                        <SyntaxHighlighter
                                                            language={match[1]}
                                                            style={syntaxStyle}
                                                            customStyle={{
                                                                margin: '0.25rem 0',
                                                                borderRadius: '0.5rem',
                                                                fontSize: '0.75rem',
                                                                padding: '0.75rem',
                                                                background: isDark ? 'rgba(17, 24, 39, 0.8)' : 'rgba(249, 250, 251, 0.95)'
                                                            }}
                                                        >
                                                            {String(children).replace(/\n$/, '')}
                                                        </SyntaxHighlighter>
                                                    ) : (
                                                        <code className={cn(
                                                            "px-1 py-0.5 rounded text-[12px] font-mono",
                                                            isDark
                                                                ? "bg-gray-800 text-gray-300"
                                                                : "bg-gray-100 text-gray-800"
                                                        )} {...rest}>
                                                            {children}
                                                        </code>
                                                    );
                                                }
                                            }}
                                        >
                                            {completion}
                                        </ReactMarkdown>
                                    ) : null}
                                </div>
                            </div>
                        )}

                        {/* Entities Tab Content - Always rendered but hidden when not active */}
                        {(results.length > 0 || isSearching) && (
                            <div style={{ display: activeTab === 'entities' ? 'block' : 'none' }}>
                                <div className={cn(
                                    "overflow-auto max-h-[438px]",
                                    isDark ? "bg-gray-900" : "bg-white"
                                )}>
                                    {isSearching ? (
                                        <div className={cn(
                                            DESIGN_SYSTEM.spacing.padding.default,
                                            "animate-pulse space-y-2"
                                        )}>
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
                                        <div className={cn(
                                            DESIGN_SYSTEM.spacing.padding.compact,
                                            DESIGN_SYSTEM.typography.sizes.label
                                        )} ref={jsonViewerRef}>
                                            <JsonViewer
                                                value={results}
                                                theme={isDark ? "dark" : "light"}
                                                style={{
                                                    fontSize: '0.62rem',
                                                    fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace',
                                                }}
                                                rootName={false}
                                                displayDataTypes={false}
                                                enableClipboard={false}
                                                quotesOnKeys={false}
                                                indentWidth={2}
                                                collapseStringsAfterLength={100}
                                                groupArraysAfterLength={100}
                                                defaultInspectDepth={10}
                                                defaultInspectControl={(path, value) => {
                                                    // Collapse airweave_system_metadata by default
                                                    if (path.includes('airweave_system_metadata')) {
                                                        return false;
                                                    }
                                                    // Expand all other nodes by default for better entity visibility
                                                    return true;
                                                }}
                                            />
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </CollapsibleCard>
    );
};
