import React, { useState, useCallback, useMemo, useRef, useEffect, startTransition } from 'react';
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
import { DESIGN_SYSTEM } from '@/lib/design-system';
import { CollapsibleCard } from '@/components/ui/CollapsibleCard';
import { FiLayers, FiFilter, FiSliders, FiList, FiClock, FiGitMerge, FiType } from "react-icons/fi";
import { ChartScatter } from 'lucide-react';
import type { SearchEvent } from '@/search/types';
import { EntityResultCard } from './EntityResultCard';

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
    const [activeTab, setActiveTab] = useState<'trace' | 'answer' | 'entities' | 'raw'>(
        responseType === 'completion' ? 'answer' : 'entities'
    );

    // Track if we've auto-switched tabs after search completion to avoid overriding manual user selection
    const hasAutoSwitchedRef = useRef(false);

    // Reset visible results count and raw JSON view when new search starts
    useEffect(() => {
        if (isSearching) {
            setVisibleResultsCount(INITIAL_RESULTS_LIMIT);
            setShowFullRawJson(false);
        }
    }, [isSearching]);

    // State for tooltip management
    const [openTooltip, setOpenTooltip] = useState<string | null>(null);
    const tooltipTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const [hoveredTooltipContent, setHoveredTooltipContent] = useState<string | null>(null);

    // Ref for JSON viewer container for scrolling to entities
    const jsonViewerRef = useRef<HTMLDivElement>(null);

    // Pagination state for entities tab (show 25 initially for performance)
    const INITIAL_RESULTS_LIMIT = 25;
    const LOAD_MORE_INCREMENT = 25;
    const [visibleResultsCount, setVisibleResultsCount] = useState(INITIAL_RESULTS_LIMIT);

    // Raw tab truncation state (show 500 lines initially for performance)
    const RAW_JSON_LINE_LIMIT = 500;
    const [showFullRawJson, setShowFullRawJson] = useState(false);

    // Extract data from response
    const statusCode = searchResponse?.error ? (searchResponse?.status ?? 500) : 200;
    const responseTime = searchResponse?.responseTime || null;
    const completion = searchResponse?.completion || '';
    const citations = searchResponse?.citations || [];
    const results = searchResponse?.results || [];
    const hasError = Boolean(searchResponse?.error);
    const isTransientError = Boolean(searchResponse?.errorIsTransient);
    const errorDisplayMessage = isTransientError
        ? "Something went wrong, please try again."
        : searchResponse?.error;

    // Debug logging
    useEffect(() => {
        console.log('[SearchResponseDisplay] State changed:', {
            isSearching,
            responseType,
            hasSearchResponse: !!searchResponse,
            completionLength: completion?.length,
            completionPreview: completion?.substring(0, 50) + (completion?.length > 50 ? '...' : ''),
            resultsCount: results?.length,
            hasError,
            activeTab,
            willReturnNull: !searchResponse && !isSearching
        });

        if (!searchResponse && !isSearching) {
            console.warn('[SearchResponseDisplay] Component will return NULL on next render!');
        }
    }, [isSearching, responseType, searchResponse, completion, results, hasError, activeTab]);


    // Memoize expensive style objects
    const syntaxStyle = useMemo(() => isDark ? materialOceanic : oneLight, [isDark]);

    // Create a mapping of entity IDs to source names and numbers
    // ALSO create a mapping of result numbers to entity IDs (for LLM citations that use numbers)
    const { entitySourceMap, resultNumberMap } = useMemo(() => {
        const map = new Map<string, { source: string; number: number }>();
        const numberMap = new Map<string, string>(); // result number -> entity ID

        // Helper function to format source names
        const formatSourceName = (name: string) => {
            return name
                .split('_')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
                .join(' ');
        };

        results.forEach((result: any, idx: number) => {
            const entityId = result.entity_id;
            const rawSourceName = result.system_metadata?.source_name || result.airweave_system_metadata?.source_name || 'Unknown';
            const sourceName = formatSourceName(rawSourceName);

            if (entityId) {
                // Store the mapping by entity ID
                // Use the global result number (1-based), not per-source count
                const resultNumber = idx + 1;
                map.set(entityId, {
                    source: sourceName,
                    number: resultNumber
                });

                // ALSO store mapping by result number string (1-based)
                // This handles LLM citations like [[1]], [[2]], [[39]], etc.
                numberMap.set(String(resultNumber), entityId);
            }
        });

        return { entitySourceMap: map, resultNumberMap: numberMap };
    }, [results]);

    // Resolve citation entity_ids to display names + sources for the references footer
    const citationEntities = useMemo(() => {
        if (!citations || citations.length === 0 || results.length === 0) return [];

        const formatSourceName = (name: string) => {
            return name
                .split('_')
                .map((word: string) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
                .join(' ');
        };

        // Deduplicate by entity_id
        const seen = new Set<string>();
        return citations
            .map((citation: any) => {
                const entityId = citation.entity_id;
                if (!entityId || seen.has(entityId)) return null;
                seen.add(entityId);
                const result = results.find((r: any) => r.entity_id === entityId);
                if (!result) return null;
                const rawSource = result.airweave_system_metadata?.source_name
                    || result.system_metadata?.source_name
                    || 'Unknown';
                return {
                    entity_id: entityId,
                    name: result.name || entityId,
                    source: formatSourceName(rawSource),
                };
            })
            .filter(Boolean) as { entity_id: string; name: string; source: string }[];
    }, [citations, results]);

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
        if (activeTab === 'raw' && searchResponse) {
            // Always copy the FULL JSON, regardless of truncation state
            await navigator.clipboard.writeText(JSON.stringify(searchResponse, null, 2));
            return;
        }
        if (responseType === 'completion' && activeTab === 'answer' && completion) {
            await handleCopyCompletion();
        } else if (activeTab === 'entities' && results.length > 0) {
            await handleCopyJson();
        }
    }, [activeTab, responseType, completion, results, searchResponse, handleCopyCompletion, handleCopyJson]);

    // Auto-scroll Trace to bottom on new events while searching, unless user scrolled up
    useEffect(() => {
        if (!isSearching) return;
        if (!traceAutoScroll) return;
        const el = traceContainerRef.current;
        if (!el) return;
        el.scrollTop = el.scrollHeight;
    }, [events?.length, isSearching, traceAutoScroll]);

    // Helper function to scroll to and highlight an entity card
    const scrollToEntity = useCallback((entityIndex: number, entityId: string) => {
        if (!jsonViewerRef.current) {
            return;
        }

        const container = jsonViewerRef.current;

        // Find the EntityResultCard by its data-entity-id attribute (most reliable)
        const targetCard = container.querySelector(`[data-entity-id="${entityId}"]`) as HTMLElement;

        if (targetCard) {

            // Scroll the card into view with some offset from top
            targetCard.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
                inline: 'nearest'
            });

            // Add highlight effect with border for better visibility
            const originalBg = targetCard.style.backgroundColor;
            const originalTransition = targetCard.style.transition;
            const originalBorder = targetCard.style.border;

            targetCard.style.transition = 'all 0.3s ease';
            targetCard.style.backgroundColor = isDark ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.15)';
            targetCard.style.border = isDark ? '2px solid rgba(59, 130, 246, 0.5)' : '2px solid rgba(59, 130, 246, 0.4)';

            // Remove highlight after 2 seconds
            setTimeout(() => {
                targetCard.style.backgroundColor = originalBg;
                targetCard.style.border = originalBorder;
                setTimeout(() => {
                    targetCard.style.transition = originalTransition;
                }, 300);
            }, 2000);
        }
    }, [isDark]);

    // Handle clicking on entity references in completion
    const handleEntityClick = useCallback((entityId: string) => {
        // Switch to entities tab
        setActiveTab('entities');

        // Wait for tab switch to complete, then scroll to entity
        setTimeout(() => {
            // Find the entity in the results array
            const entityIndex = results.findIndex((result: any) => {
                return result.entity_id === entityId;
            });

            if (entityIndex === -1) {
                return;
            }

            // Check if entity is in visible results (pagination issue)
            if (entityIndex >= visibleResultsCount) {

                // Expand visible results to include this entity
                setVisibleResultsCount(entityIndex + 1);

                // Wait for React to render the new results, then scroll
                // Use multiple animation frames to ensure DOM is fully updated
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        setTimeout(() => {
                            scrollToEntity(entityIndex, entityId);
                        }, 100);
                    });
                });
            } else {
                // Entity is already visible, scroll immediately after DOM update
                requestAnimationFrame(() => {
                    scrollToEntity(entityIndex, entityId);
                });
            }
        }, 150);
    }, [results, visibleResultsCount, scrollToEntity]);

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
            spanSeconds: null as number | null,
            supportingSources: null as string[] | null,
            sourceFilteringEnabled: false
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

            // ─── Agentic search events ───────────────────────────────────
            if (event.type === 'planning') {
                const plan = event.plan;
                rows.push(
                    <div key={`planning-${i}`} className="animate-fade-in space-y-1.5 py-1.5">
                        {plan?.reasoning && (
                            <div className={cn(
                                "text-[11px] leading-relaxed",
                                isDark ? "text-gray-400" : "text-gray-500"
                            )}>
                                {plan.reasoning}
                            </div>
                        )}
                    </div>
                );
                continue;
            }

            if (event.type === 'searching') {
                rows.push(
                    <div key={`searching-${i}`} className={cn(
                        "animate-fade-in flex items-center gap-2 py-0.5 text-[10px]",
                        isDark ? "text-gray-500" : "text-gray-400"
                    )}>
                        <span>
                            Retrieved <span className={cn("font-medium", isDark ? "text-gray-300" : "text-gray-600")}>{event.result_count}</span> results in <span className={cn("font-medium", isDark ? "text-gray-300" : "text-gray-600")}>{event.duration_ms}ms</span>
                        </span>
                    </div>
                );
                continue;
            }

            if (event.type === 'evaluating') {
                const eval_ = event.evaluation;
                if (eval_?.reasoning) {
                    rows.push(
                        <div key={`evaluating-${i}`} className="animate-fade-in py-0.5">
                            <div className={cn(
                                "text-[11px] leading-relaxed",
                                isDark ? "text-gray-400" : "text-gray-500"
                            )}>
                                {eval_.reasoning}
                            </div>
                        </div>
                    );
                }
                continue;
            }

            // Operation skipped notices (backend emits when ops are not applicable)
            if (event.type === 'operation_skipped') {
                const op = (event as any).operation || 'operation';
                const reason = (event as any).reason || 'skipped';

                // User-friendly messages for skip reasons
                const skipMessages: Record<string, string> = {
                    'no_sources_support_temporal_relevance': 'Sources in this collection do not support recency bias',
                    'All sources in the collection use federated search': 'All sources use federated search',
                };

                const displayMessage = skipMessages[reason] || `${reason}`;

                rows.push(
                    <div key={`skipped-${i}`} className="py-0.5 px-2 text-[11px] opacity-80">
                        • Skipped {op}: {displayMessage}
                    </div>
                );
                rows.push(
                    <div key={`skipped-${i}-separator`} className="py-1">
                        <div className="mx-2 border-t border-border/30"></div>
                    </div>
                );
                continue;
            }


            if (event.type === 'operator_start' && (event.op === 'qdrant_filter' || event.op === 'vespa_filter')) {
                const filterOp = event.op;
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
                    if ((src[j] as any).type === 'operator_end' && (src[j] as any).op === filterOp) {
                        break;
                    }
                }

                rows.push(
                    <div key={`filter-${i}-start`} className="px-2 py-1 text-[11px] flex items-center gap-1.5">
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
                        <div key={`filter-${i}-merge-label`} className="px-2 py-0.5 text-[11px] opacity-70">
                            merged interpreted + manual
                        </div>
                    );
                }

                if (filterData && typeof filterData === 'object') {
                    const display = toDisplayFilter(filterData);
                    const pretty = JSON.stringify(display, null, 2);
                    rows.push(
                        <div key={`filter-data-${i}`} className="py-0.5 px-2 text-[11px]">
                            <span className="opacity-90">• Filter:</span>
                            <div className="ml-3 mt-1">
                                <JsonBlock value={pretty} isDark={isDark} />
                            </div>
                        </div>
                    );
                }

                while (i < src.length && !((src[i] as any).type === 'operator_end' && (src[i] as any).op === filterOp)) {
                    i++;
                }

                if (i < src.length) {
                    rows.push(
                        <div key={`filter-${i}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                            Filter applied
                        </div>
                    );

                    rows.push(
                        <div key={`filter-${i}-separator`} className="py-1">
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

                if (event.type === 'filter_applied') {
                    interpretationData.filterApplied = (event as any).filter;
                    continue;
                }

                if (event.type === 'operator_end' && event.op === 'query_interpretation') {
                    const key = `interp-${i}`;

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

            if (event.type === 'operator_start' && event.op === 'federated_search') {
                const federatedSearchData = {
                    numSources: 0,
                    sourceNames: [] as string[],
                    numQueries: 1,
                    numKeywords: 0,
                    keywords: [] as string[],
                    federatedCount: 0,
                    vectorCount: 0,
                    mergedCount: 0,
                    noResults: false
                };
                let j = i + 1;
                while (j < src.length && (src[j] as any).type !== 'operator_end') {
                    const nextEvent = src[j] as any;
                    if (nextEvent.type === 'federated_search_start') {
                        federatedSearchData.numSources = nextEvent.num_sources || 0;
                        federatedSearchData.sourceNames = nextEvent.source_names || [];
                        federatedSearchData.numQueries = nextEvent.num_queries || 1;
                        federatedSearchData.numKeywords = nextEvent.num_keywords || 0;
                        federatedSearchData.keywords = nextEvent.keywords || [];
                    } else if (nextEvent.type === 'federated_search_done') {
                        federatedSearchData.federatedCount = nextEvent.federated_count || 0;
                        federatedSearchData.vectorCount = nextEvent.vector_count || 0;
                        federatedSearchData.mergedCount = nextEvent.merged_count || 0;
                    } else if (nextEvent.type === 'federated_search_no_results') {
                        federatedSearchData.noResults = true;
                        federatedSearchData.vectorCount = nextEvent.vector_count || 0;
                    }
                    j++;
                }

                const key = `federated-${i}`;
                rows.push(
                    <div key={`${key}-start`} className="px-2 py-1 text-[11px] flex items-center gap-1.5">
                        <FiSliders className="h-3 w-3 opacity-80" />
                        <span className="opacity-90">Federated Search</span>
                        <span className={cn(
                            "ml-1 px-1 py-0 rounded text-[10px]",
                            isDark ? "bg-gray-800 text-gray-300" : "bg-gray-100 text-gray-700"
                        )}>{federatedSearchData.sourceNames.join(', ')}</span>
                        {federatedSearchData.numQueries > 1 && (
                            <span className={cn(
                                "ml-1 px-1 py-0 rounded text-[10px]",
                                isDark ? "bg-blue-900/40 text-blue-300" : "bg-blue-100 text-blue-700"
                            )}>{federatedSearchData.numQueries} queries</span>
                        )}
                    </div>
                );

                // Show extracted keywords
                if (federatedSearchData.keywords.length > 0) {
                    rows.push(
                        <div key={`${key}-keywords-header`} className="py-0.5 px-2 text-[11px] opacity-90">
                            Searching with {federatedSearchData.numKeywords} keyword{federatedSearchData.numKeywords !== 1 ? 's' : ''}:
                        </div>
                    );
                    federatedSearchData.keywords.forEach((keyword, idx) => {
                        rows.push(
                            <div key={`${key}-keyword-${idx}`} className="py-0.5 px-2 pl-4 text-[11px] opacity-80">
                                • {keyword}
                            </div>
                        );
                    });
                }

                if (federatedSearchData.noResults) {
                    rows.push(
                        <div key={`${key}-no-results`} className="py-0.5 px-2 text-[11px] opacity-80">
                            No results from federated sources
                        </div>
                    );
                } else if (federatedSearchData.mergedCount > 0) {
                    rows.push(
                        <div key={`${key}-merged`} className="py-0.5 px-2 text-[11px] opacity-80">
                            Merged {federatedSearchData.federatedCount} federated + {federatedSearchData.vectorCount} vector = {federatedSearchData.mergedCount} results
                        </div>
                    );
                }

                rows.push(
                    <div key={`${key}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                        Federated search complete
                    </div>
                );
                rows.push(
                    <div key={`${key}-separator`} className="py-1">
                        <div className="mx-2 border-t border-border/30"></div>
                    </div>
                );

                while (i < src.length && !((src[i] as any).type === 'operator_end' && (src[i] as any).op === 'federated_search')) {
                    i++;
                }
                continue;
            }

            if (event.type === 'operator_start' && event.op === 'vector_search') {
                const vectorSearchData = {
                    method: null as string | null,
                    finalCount: null as number | null,
                    topScores: [] as number[],
                    noResults: false,
                    hasFilter: false
                };
                let j = i + 1;
                while (j < src.length && (src[j] as any).type !== 'operator_end') {
                    const nextEvent = src[j] as any;
                    if (nextEvent.type === 'vector_search_start') {
                        vectorSearchData.method = nextEvent.method;
                    } else if (nextEvent.type === 'vector_search_done') {
                        vectorSearchData.finalCount = nextEvent.final_count;
                        vectorSearchData.topScores = nextEvent.top_scores || [];
                    } else if (nextEvent.type === 'vector_search_no_results') {
                        vectorSearchData.noResults = true;
                        vectorSearchData.hasFilter = nextEvent.has_filter || false;
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

                if (vectorSearchData.noResults) {
                    // Special message for zero results
                    const noResultsMessage = vectorSearchData.hasFilter
                        ? "No documents in the database match the search query and applied filters"
                        : "No documents in the database match the search query";
                    rows.push(
                        <div key={`${key}-no-results`} className="py-0.5 px-2 text-[11px] opacity-80">
                            {noResultsMessage}
                        </div>
                    );
                } else if (vectorSearchData.finalCount !== null) {
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
                    spanSeconds: null,
                    supportingSources: null,
                    sourceFilteringEnabled: false
                };
                continue;
            }
            if (inRecency) {
                if (event.type === 'recency_start') {
                    const e = event as any;
                    const weight = e.requested_weight;
                    if (typeof weight === 'number') {
                        recencyData.weight = weight;
                    }
                    if (e.source_filtering_enabled) {
                        recencyData.sourceFilteringEnabled = true;
                        recencyData.supportingSources = e.supporting_sources || [];
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
                    const reasonMessages: Record<string, string> = {
                        'no_documents_in_filtered_space': 'No documents match the applied filters',
                        'no_valid_timestamps': 'No valid timestamps found in matching documents',
                        'no_timestamps': 'No timestamps available',
                        'weight_zero': 'Recency weight set to zero',
                        'invalid_range': 'Invalid time range detected',
                        'zero_span': 'Time span is zero',
                        'zero_or_negative_span': 'All documents have the same timestamp',
                    };
                    const displayMessage = reasonMessages[reason] || reason;
                    rows.push(
                        <div key={`recency-skip-${i}`} className={cn(
                            "py-0.5 px-2 text-[11px]",
                            reason === 'no_documents_in_filtered_space' ? "" : ""
                        )}>
                            • Recency bias skipped: {displayMessage}
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
                    if (recencyData.sourceFilteringEnabled && recencyData.supportingSources) {
                        const sources = recencyData.supportingSources as string[];
                        rows.push(
                            <div key={`${key}-source-filter`} className="py-0.5 px-2 text-[11px] opacity-80">
                                Searching only sources with timestamps: {sources.join(', ')}
                            </div>
                        );
                    }
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
                // New simplified single-shot rankings snapshot
                if (event.type === 'rankings') {
                    const rankings = (event as any).rankings;
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
                                Top {rerankingData.rankings.length} result{rerankingData.rankings.length !== 1 ? 's' : ''}:
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

            // Handle answer generation events
            if (event.type === 'operator_start' && event.op === 'completion') {
                rows.push(
                    <div key={`completion-${i}-start`} className="px-2 py-1 text-[11px] flex items-center gap-1.5">
                        <FiMessageSquare className="h-3 w-3 opacity-80" />
                        <span className="opacity-90">Answer generation</span>
                    </div>
                );
                continue;
            }

            if (event.type === 'answer_context_budget') {
                const e = event as any;
                rows.push(
                    <div key={`completion-budget-${i}`} className="py-0.5 px-2 text-[11px] opacity-80">
                        Using {e.results_in_context} of {e.total_results} result{e.total_results !== 1 ? 's' : ''} in context
                        {e.excluded > 0 && (
                            <span className="opacity-70"> ({e.excluded} excluded due to token limit)</span>
                        )}
                    </div>
                );
                continue;
            }

            if (event.type === 'operator_end' && event.op === 'completion') {
                rows.push(
                    <div key={`completion-${i}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                        Answer generation complete
                    </div>
                );
                rows.push(
                    <div key={`completion-${i}-separator`} className="py-1">
                        <div className="mx-2 border-t border-border/30"></div>
                    </div>
                );
                continue;
            }

            if (event.type === 'completion_done') {
                continue; // Don't show in trace, just for aggregation
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
                continue;
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
        if (isSearching) {
            setActiveTab('trace');
            hasAutoSwitchedRef.current = false; // Reset flag when new search starts
        }
    }, [isSearching]);

    useEffect(() => {
        // When completion arrives (not streaming anymore), switch to answer tab
        if (responseType === 'completion' && !isSearching && completion && completion.length > 0) {
            if (activeTab === 'trace' && !hasAutoSwitchedRef.current) {
                setActiveTab('answer');
                hasAutoSwitchedRef.current = true;
            }
        }
    }, [responseType, isSearching, completion]);

    useEffect(() => {
        if (responseType === 'raw' && !isSearching && Array.isArray(results) && results.length > 0) {
            if (!hasAutoSwitchedRef.current) {
                setActiveTab('entities');
                hasAutoSwitchedRef.current = true;
            }
        }
    }, [responseType, isSearching, results]);

    // Guard: show nothing if no response and not loading (after hooks per lint rules)
    if (!searchResponse && !isSearching) {
        return null;
    }

    // Create header content with status information
    const headerContent = (
        <>
            <span className={cn(DESIGN_SYSTEM.typography.sizes.label, "opacity-80")}>Response</span>
            <div className="flex items-center gap-3">
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
                        <span className="font-mono">{(responseTime / 1000).toFixed(2)}s</span>
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
                <div
                    className={cn(
                        "absolute inset-0 h-1.5 bg-gradient-to-r",
                        hasError
                            ? isTransientError
                                ? "from-gray-200 to-gray-300 dark:from-gray-700 dark:to-gray-600"
                                : "from-red-500 to-red-600"
                            : "from-green-500 to-emerald-500"
                    )}
                ></div>
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
                        isTransientError
                            ? isDark
                                ? "border-gray-800/50 bg-gray-900/40"
                                : "border-gray-200/70 bg-gray-50"
                            : isDark
                                ? "border-gray-800/50 bg-red-950/20"
                                : "border-gray-200/50 bg-red-50"
                    )}>
                        <div className={cn(
                            "text-sm",
                            isTransientError
                                ? isDark
                                    ? "text-gray-100"
                                    : "text-gray-700"
                                : isDark
                                    ? "text-red-300"
                                    : "text-red-700"
                        )}>
                            {errorDisplayMessage}
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
                                onClick={() => startTransition(() => setActiveTab('trace'))}
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
                                        onClick={() => startTransition(() => setActiveTab('entities'))}
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

                                    {/* Raw (middle-right) */}
                                    <button
                                        onClick={() => startTransition(() => setActiveTab('raw'))}
                                        className={cn(
                                            "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                            activeTab === 'raw'
                                                ? isDark
                                                    ? "text-white bg-gray-800/70"
                                                    : "text-gray-900 bg-white"
                                                : isDark
                                                    ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30"
                                                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                                        )}
                                    >
                                        <div className="flex items-center gap-1.5">
                                            <Braces className="h-3 w-3" strokeWidth={1.5} />
                                            Raw
                                        </div>
                                        {activeTab === 'raw' && (
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
                                        onClick={() => startTransition(() => setActiveTab('answer'))}
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

                                    {/* Entities (middle-right) */}
                                    <button
                                        onClick={() => startTransition(() => setActiveTab('entities'))}
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

                                    {/* Raw (right) */}
                                    <button
                                        onClick={() => startTransition(() => setActiveTab('raw'))}
                                        className={cn(
                                            "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                            activeTab === 'raw'
                                                ? isDark
                                                    ? "text-white bg-gray-800/70"
                                                    : "text-gray-900 bg-white"
                                                : isDark
                                                    ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30"
                                                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                                        )}
                                    >
                                        <div className="flex items-center gap-1.5">
                                            <Braces className="h-3 w-3" strokeWidth={1.5} />
                                            Raw
                                        </div>
                                        {activeTab === 'raw' && (
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
                        {activeTab === 'trace' && (
                            <div ref={traceContainerRef} onScroll={handleTraceScroll} className={cn(
                                "overflow-auto max-h-[700px] raw-data-scrollbar",
                                DESIGN_SYSTEM.spacing.padding.compact,
                                isDark ? "bg-gray-950" : "bg-white"
                            )}>
                                {(!events || events.length === 0) ? (
                                    <div className="animate-fade-in px-1 py-2 flex items-center gap-2">
                                        <span className={cn(
                                            "inline-block h-1 w-1 rounded-full animate-pulse shrink-0",
                                            isDark ? "bg-gray-500" : "bg-gray-400"
                                        )} />
                                        <span className={cn("text-[11px]", isDark ? "text-gray-500" : "text-gray-400")}>
                                            {responseType === 'completion' ? 'Planning search strategy...' : 'Starting search...'}
                                        </span>
                                    </div>
                                ) : (
                                    <>
                                        {traceRows}
                                        {events.some((e: any) => e?.type === 'cancelled') && (
                                            <div className="py-0.5 px-2 text-[11px] text-red-500">
                                                Search cancelled
                                            </div>
                                        )}
                                    </>
                                )}
                            </div>
                        )}

                        {/* Answer Tab Content */}
                        {activeTab === 'answer' && responseType === 'completion' && (completion || isSearching) && (
                            <div>
                                <div className={cn(
                                    "overflow-auto max-h-[700px] leading-relaxed raw-data-scrollbar",
                                    DESIGN_SYSTEM.spacing.padding.compact,
                                    DESIGN_SYSTEM.typography.sizes.body,
                                    isDark ? "bg-gray-900 text-gray-200" : "bg-white text-gray-800"
                                )}>
                                    {isSearching ? (
                                        // Show skeleton while searching (completion not streamed anymore)
                                        <div className="animate-pulse h-32 w-full">
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-5/6 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-2/3 mb-2.5"></div>
                                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
                                        </div>
                                    ) : completion ? (
                                        // Show the actual completion (only available when search completes)
                                        <div className="animate-fade-in"><ReactMarkdown
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
                                                a: ({ node, href, children, ...props }) => {
                                                    // Check if this is a malformed citation
                                                    // Pattern 1: href like "Result 5" or "5"
                                                    const hrefPattern = /^(?:Result\s+)?(\d+)$/i;
                                                    const hrefMatch = href?.match(hrefPattern);

                                                    // Pattern 2: children text like "[Result 75]" or "[5]"
                                                    // (happens when LLM writes [[Result 75]](url))
                                                    const childText = typeof children === 'string' ? children : '';
                                                    const childPattern = /^\[(?:Result\s+)?(\d+)\]$/i;
                                                    const childMatch = childText.match(childPattern);

                                                    // Extract result number from either pattern
                                                    const resultNumber = hrefMatch?.[1] || childMatch?.[1];

                                                    if (resultNumber) {
                                                        // This is a citation, render as button (ignoring the URL)
                                                        const mappedId = resultNumberMap.get(resultNumber);
                                                        const resolvedEntityId = mappedId || resultNumber;
                                                        const sourceInfo = entitySourceMap.get(resolvedEntityId);

                                                        const displayText = sourceInfo
                                                            ? `${sourceInfo.source} [${sourceInfo.number}]`
                                                            : `[${resultNumber}]`;

                                                        const tooltipText = sourceInfo
                                                            ? `Click to view ${sourceInfo.source} entity #${sourceInfo.number} in the Entities tab`
                                                            : `Click to view entity: ${resultNumber}`;

                                                        return (
                                                            <button
                                                                onClick={() => handleEntityClick(resolvedEntityId)}
                                                                className={cn(
                                                                    "inline-flex items-center gap-0.5 px-1 py-0.5 rounded-md text-[11px] font-medium",
                                                                    "transition-colors cursor-pointer",
                                                                    isDark
                                                                        ? "bg-blue-950/50 text-blue-300 hover:bg-blue-900/70 hover:text-blue-200"
                                                                        : "bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700",
                                                                    "border",
                                                                    isDark ? "border-blue-800/50" : "border-blue-200"
                                                                )}
                                                                title={tooltipText}
                                                            >
                                                                {displayText}
                                                            </button>
                                                        );
                                                    }

                                                    // Regular link - render normally
                                                    return (
                                                        <a
                                                            href={href}
                                                            className={cn(
                                                                "underline",
                                                                isDark ? "text-blue-400 hover:text-blue-300" : "text-blue-600 hover:text-blue-700"
                                                            )}
                                                            {...props}
                                                        >
                                                            {children}
                                                        </a>
                                                    );
                                                },
                                                li: ({ children, ...props }) => {
                                                    // Process list item content to replace citations with clickable links
                                                    const processedChildren = React.Children.map(children, (child) => {
                                                        if (typeof child === 'string') {
                                                            // Split by citation patterns: [[...]] or 【...】
                                                            const parts = child.split(/(\[\[[^\]]+\]\]|【[^】]+】)/g);
                                                            return parts.map((part, index) => {
                                                                // Match either [[...]] or 【...】
                                                                const match = part.match(/^(?:\[\[([^\]]+)\]\]|【([^】]+)】)$/);
                                                                if (match) {
                                                                    // Extract citation content (from either capture group)
                                                                    let citationRef = match[1] || match[2];

                                                                    // Handle "Results 36-37" or "Result 5" format
                                                                    // Extract just the numbers
                                                                    const numbersMatch = citationRef.match(/(\d+)(?:[-–‑](\d+))?/);
                                                                    if (numbersMatch) {
                                                                        // For ranges like "36-37", use the first number
                                                                        citationRef = numbersMatch[1];
                                                                    }

                                                                    // Try to resolve citation ref to entity ID
                                                                    // LLM might cite by result number (e.g., [[39]]) or by UUID
                                                                    let resolvedEntityId = citationRef;

                                                                    // Check if this is a result number citation (e.g., "39", "1", "100")
                                                                    if (/^\d+$/.test(citationRef)) {
                                                                        const mappedId = resultNumberMap.get(citationRef);
                                                                        if (mappedId) {
                                                                            resolvedEntityId = mappedId;
                                                                        }
                                                                    }

                                                                    const sourceInfo = entitySourceMap.get(resolvedEntityId);

                                                                    const displayText = sourceInfo
                                                                        ? `${sourceInfo.source} [${sourceInfo.number}]`
                                                                        : citationRef;

                                                                    const tooltipText = sourceInfo
                                                                        ? `Click to view ${sourceInfo.source} entity #${sourceInfo.number} in the Entities tab`
                                                                        : `Click to view entity: ${citationRef}`;

                                                                    return (
                                                                        <button
                                                                            key={index}
                                                                            onClick={() => handleEntityClick(resolvedEntityId)}
                                                                            className={cn(
                                                                                "inline-flex items-center gap-0.5 px-1 py-0.5 rounded-md text-[11px] font-medium",
                                                                                "transition-colors cursor-pointer",
                                                                                isDark
                                                                                    ? "bg-blue-950/50 text-blue-300 hover:bg-blue-900/70 hover:text-blue-200"
                                                                                    : "bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700",
                                                                                "border",
                                                                                isDark ? "border-blue-800/50" : "border-blue-200"
                                                                            )}
                                                                            title={tooltipText}
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
                                                    // Process paragraph content to replace citations with clickable links
                                                    const processedChildren = React.Children.map(children, (child) => {
                                                        if (typeof child === 'string') {
                                                            // Split by citation patterns: [[...]] or 【...】
                                                            const parts = child.split(/(\[\[[^\]]+\]\]|【[^】]+】)/g);
                                                            return parts.map((part, index) => {
                                                                // Match either [[...]] or 【...】
                                                                const match = part.match(/^(?:\[\[([^\]]+)\]\]|【([^】]+)】)$/);
                                                                if (match) {
                                                                    // Extract citation content (from either capture group)
                                                                    let citationRef = match[1] || match[2];

                                                                    // Handle "Results 36-37" or "Result 5" format
                                                                    // Extract just the numbers
                                                                    const numbersMatch = citationRef.match(/(\d+)(?:[-–‑](\d+))?/);
                                                                    if (numbersMatch) {
                                                                        // For ranges like "36-37", use the first number
                                                                        citationRef = numbersMatch[1];
                                                                    }

                                                                    // Try to resolve citation ref to entity ID
                                                                    // LLM might cite by result number (e.g., [[39]]) or by UUID
                                                                    let resolvedEntityId = citationRef;

                                                                    // Check if this is a result number citation (e.g., "39", "1", "100")
                                                                    if (/^\d+$/.test(citationRef)) {
                                                                        const mappedId = resultNumberMap.get(citationRef);
                                                                        if (mappedId) {
                                                                            resolvedEntityId = mappedId;
                                                                        }
                                                                    }

                                                                    const sourceInfo = entitySourceMap.get(resolvedEntityId);

                                                                    const displayText = sourceInfo
                                                                        ? `${sourceInfo.source} [${sourceInfo.number}]`
                                                                        : citationRef;

                                                                    const tooltipText = sourceInfo
                                                                        ? `Click to view ${sourceInfo.source} entity #${sourceInfo.number} in the Entities tab`
                                                                        : `Click to view entity: ${citationRef}`;

                                                                    return (
                                                                        <button
                                                                            key={index}
                                                                            onClick={() => handleEntityClick(resolvedEntityId)}
                                                                            className={cn(
                                                                                "inline-flex items-center gap-0.5 px-1 py-0.5 rounded-md text-[11px] font-medium",
                                                                                "transition-colors cursor-pointer",
                                                                                isDark
                                                                                    ? "bg-blue-950/50 text-blue-300 hover:bg-blue-900/70 hover:text-blue-200"
                                                                                    : "bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700",
                                                                                "border",
                                                                                isDark ? "border-blue-800/50" : "border-blue-200"
                                                                            )}
                                                                            title={tooltipText}
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
                                            {completion.replace(/\\n/g, '\n')}
                                        </ReactMarkdown></div>
                                    ) : null}
                                </div>

                                {/* References footer */}
                                {!isSearching && citationEntities.length > 0 && (
                                    <div className={cn(
                                        "animate-fade-in border-t px-4 py-3",
                                        isDark ? "border-gray-800/50" : "border-gray-200/50"
                                    )}>
                                        <div className={cn(
                                            "text-[10px] font-medium uppercase tracking-wider mb-2",
                                            isDark ? "text-gray-500" : "text-gray-400"
                                        )}>
                                            Sources
                                        </div>
                                        <div className="flex flex-wrap gap-1.5">
                                            {citationEntities.map((entity) => (
                                                <button
                                                    key={entity.entity_id}
                                                    onClick={() => handleEntityClick(entity.entity_id)}
                                                    className={cn(
                                                        "inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px]",
                                                        "transition-colors cursor-pointer max-w-[280px]",
                                                        isDark
                                                            ? "bg-gray-800/60 text-gray-300 hover:bg-gray-700/80 hover:text-gray-100 border border-gray-700/50"
                                                            : "bg-gray-50 text-gray-700 hover:bg-gray-100 hover:text-gray-900 border border-gray-200"
                                                    )}
                                                    title={`${entity.name} — ${entity.source}`}
                                                >
                                                    <span className="truncate font-medium">{entity.name}</span>
                                                    <span className={cn(
                                                        "shrink-0 text-[10px]",
                                                        isDark ? "text-gray-500" : "text-gray-400"
                                                    )}>
                                                        {entity.source}
                                                    </span>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Entities Tab Content */}
                        {activeTab === 'entities' && (results.length > 0 || isSearching) && (
                            <div className={cn(
                                "overflow-auto max-h-[700px] raw-data-scrollbar",
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
                                    <>
                                        <div
                                            ref={jsonViewerRef}
                                            className={cn(
                                                "px-4 py-3 space-y-5 raw-data-scrollbar",
                                                DESIGN_SYSTEM.typography.sizes.label
                                            )}
                                        >
                                            {results.slice(0, visibleResultsCount).map((result: any, index: number) => (
                                                <EntityResultCard
                                                    key={result.entity_id || result.id || index}
                                                    result={result}
                                                    index={index}
                                                    isDark={isDark}
                                                    onEntityIdClick={handleEntityClick}
                                                />
                                            ))}
                                        </div>

                                        {/* Load More Button */}
                                        {results.length > visibleResultsCount && (
                                            <div className={cn(
                                                "flex justify-center px-4 py-3 border-t",
                                                isDark ? "border-gray-800/50 bg-gray-900/50" : "border-gray-200/50 bg-gray-50/50"
                                            )}>
                                                <Button
                                                    onClick={() => setVisibleResultsCount(prev => Math.min(prev + LOAD_MORE_INCREMENT, results.length))}
                                                    variant="outline"
                                                    size="sm"
                                                    className={cn(
                                                        "text-xs font-medium",
                                                        isDark
                                                            ? "bg-gray-800 hover:bg-gray-700 border-gray-700 text-gray-200"
                                                            : "bg-white hover:bg-gray-50 border-gray-300 text-gray-700"
                                                    )}
                                                >
                                                    <Layers className="h-3.5 w-3.5 mr-1.5" />
                                                    Load More ({visibleResultsCount} of {results.length})
                                                </Button>
                                            </div>
                                        )}
                                    </>
                                )}
                            </div>
                        )}

                        {/* Raw Tab Content */}
                        {activeTab === 'raw' && (() => {
                            const fullJsonString = JSON.stringify(searchResponse, null, 2);
                            const jsonLines = fullJsonString.split('\n');
                            const shouldTruncate = jsonLines.length > RAW_JSON_LINE_LIMIT;
                            const displayString = showFullRawJson || !shouldTruncate
                                ? fullJsonString
                                : jsonLines.slice(0, RAW_JSON_LINE_LIMIT).join('\n') + '\n...';

                            // Use plain text for large JSON (>1000 lines) to avoid freezing
                            // SyntaxHighlighter chokes on huge JSON (37k+ lines can freeze for 15+ seconds)
                            const usePlainText = jsonLines.length > 1000;

                            return (
                                <>
                                    <div className={cn(
                                        "overflow-auto max-h-[700px] raw-data-scrollbar",
                                        isDark ? "bg-gray-950" : "bg-gray-50"
                                    )}>
                                        {usePlainText ? (
                                            // Plain text for large JSON - instant render, no coloring overhead
                                            <pre className={cn(
                                                "font-mono text-[11px] p-4 m-0 leading-relaxed whitespace-pre",
                                                isDark ? "text-gray-300" : "text-gray-800"
                                            )}>
                                                {displayString}
                                            </pre>
                                        ) : (
                                            // SyntaxHighlighter for small JSON - pretty colors
                                            <SyntaxHighlighter
                                                language="json"
                                                style={syntaxStyle}
                                                customStyle={{
                                                    margin: 0,
                                                    borderRadius: 0,
                                                    fontSize: '11px',
                                                    padding: '1rem',
                                                    background: 'transparent',
                                                    lineHeight: '1.5'
                                                }}
                                                showLineNumbers={false}
                                            >
                                                {displayString}
                                            </SyntaxHighlighter>
                                        )}
                                    </div>

                                    {/* Show Full JSON Button */}
                                    {shouldTruncate && !showFullRawJson && (
                                        <div className={cn(
                                            "flex items-center justify-center gap-2 px-3 py-2.5 border-t",
                                            isDark
                                                ? "border-gray-800/40 bg-gray-900/30"
                                                : "border-gray-200/60 bg-gray-50/40"
                                        )}>
                                            <button
                                                onClick={() => setShowFullRawJson(true)}
                                                className={cn(
                                                    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-150",
                                                    isDark
                                                        ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/50"
                                                        : "text-gray-500 hover:text-gray-700 hover:bg-gray-100/80"
                                                )}
                                            >
                                                <Braces className="h-3 w-3 opacity-60" />
                                                <span>Load remaining</span>
                                                <span className={cn(
                                                    "opacity-50 font-mono text-[10px]"
                                                )}>
                                                    +{(jsonLines.length - RAW_JSON_LINE_LIMIT).toLocaleString()} lines
                                                </span>
                                            </button>
                                        </div>
                                    )}
                                </>
                            );
                        })()}
                    </div>
                )
                }
            </div >
        </CollapsibleCard >
    );
};
