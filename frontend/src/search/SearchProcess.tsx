import React, { useMemo, useRef, useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import { Button } from "@/components/ui/button";
import { Copy, Check } from "lucide-react";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FiLayers, FiFilter, FiSliders, FiBox, FiList, FiClock, FiGitMerge, FiType } from "react-icons/fi";
import type { SearchEvent } from "@/search/types";
import { DESIGN_SYSTEM } from "@/lib/design-system";
import { CollapsibleCard } from "@/components/ui/CollapsibleCard";

interface SearchProcessProps {
    requestId?: string | null;
    events: any[];  // SearchEvent[] | AgenticSearchEvent[] - mixed during streaming
    className?: string;
    isSearching?: boolean;
}



export const SearchProcess: React.FC<SearchProcessProps> = ({ requestId, events, className, isSearching = false }) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    // Collapsible state with localStorage persistence
    const [isExpanded, setIsExpanded] = useState(() => {
        const stored = localStorage.getItem('searchProcess-expanded');
        return stored ? JSON.parse(stored) : true; // Default to expanded
    });

    // Persist state changes
    useEffect(() => {
        localStorage.setItem('searchProcess-expanded', JSON.stringify(isExpanded));
    }, [isExpanded]);
    useEffect(() => {
        console.log('[SearchProcess] Theme changed', { resolvedTheme, isDark });
    }, [resolvedTheme, isDark]);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const lastEventCountRef = useRef(0);
    const [copied, setCopied] = useState(false);

    // Copy entire process text
    const handleCopyProcess = useCallback(async () => {
        const text = scrollContainerRef.current?.innerText || "";
        await navigator.clipboard.writeText(text.trim());
    }, []);

    // Pretty-print helper: hide internal system prefix in keys for display only
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

    // Reusable JSON block with copy + syntax highlighting
    const JsonBlock: React.FC<{ value: string; isDark: boolean }> = ({ value, isDark }) => {
        const [copiedLocal, setCopiedLocal] = useState(false);
        const handleCopy = useCallback(async () => {
            try {
                await navigator.clipboard.writeText(value);
                setCopiedLocal(true);
                setTimeout(() => setCopiedLocal(false), 1500);
            } catch {
                // noop
            }
        }, [value]);

        useEffect(() => {
            const preview = value?.slice(0, 120) || '';
            const bg = isDark ? 'rgba(17, 24, 39, 0.8)' : 'rgba(249, 250, 251, 0.95)';
            // DEBUG: Verify theme-driven styling for JSON blocks
            console.log('[SearchProcess][JsonBlock] render', {
                isDark,
                length: value?.length,
                preview,
                background: bg
            });
        }, [isDark, value]);

        return (
            <div className="relative">
                <button
                    type="button"
                    onClick={handleCopy}
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

    // Auto-scroll to bottom when new events arrive
    useEffect(() => {
        if (events.length > lastEventCountRef.current && scrollContainerRef.current) {
            // Scroll to bottom to show latest event
            scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
        }
        lastEventCountRef.current = events.length;
    }, [events.length]);

    // Derive live/in-progress, answering, and error state from events
    const { isLive, isAnswering, hasError } = useMemo(() => {
        if (!events || events.length === 0) {
            return { isLive: false, isAnswering: false, hasError: false };
        }
        const last = events[events.length - 1] as any;
        const ended = last?.type === 'done';
        const error = events.some((e: any) => e?.type === 'error');
        const started = events.some((e: any) => e?.type === 'connected' || e?.type === 'start' || e?.type === 'operator_start' || e?.type === 'planning');
        const answering = events.some((e: any) => e?.type === 'completion_start' || e?.type === 'completion_delta');
        const cancelled = events.some((e: any) => e?.type === 'cancelled');
        return {
            isLive: started && !ended && !error && !cancelled,
            isAnswering: answering && !ended && !error && !cancelled,
            hasError: error
        };
    }, [events]);

    // Copy handler for request id
    const handleCopyId = useCallback(async () => {
        if (!requestId) return;
        try {
            await navigator.clipboard.writeText(requestId);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        } catch {
            // noop
        }
    }, [requestId]);



    // Transform events, aggregating query_interpretation and query_expansion into human-readable format
    const displayRows = useMemo(() => {
        const src = events.length > 500 ? events.slice(-500) : events;
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
        // Carry embedding details forward to combine with vector search as a single "Retrieval" section
        let pendingEmbedding: {
            searchMethod: string | null;
            neuralCount: number | null;
            sparseCount: number | null;
            dim: number | null;
            model: string | null;
        } | null = null;

        for (let i = 0; i < src.length; i++) {
            const event = src[i];
            if (i === 0) {
                console.log('[SearchProcess] Rendering events', { count: src.length, firstType: (event as any)?.type });
            }

            // ─── Agentic search events ───────────────────────────────────
            if (event.type === 'planning') {
                const e = event as any;
                const plan = e.plan;
                rows.push(
                    <div key={`planning-${i}`} className="space-y-2">
                        <div className="flex items-center gap-2">
                            <div className={cn(
                                "h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold",
                                isDark ? "bg-primary/20 text-primary" : "bg-primary/10 text-primary"
                            )}>
                                {e.iteration + 1}
                            </div>
                            <span className={cn(DESIGN_SYSTEM.typography.sizes.body, DESIGN_SYSTEM.typography.weights.semibold)}>
                                {e.is_consolidation ? 'Consolidation' : `Iteration ${e.iteration + 1}`}
                            </span>
                        </div>
                        {plan?.reasoning && (
                            <div className={cn(
                                "ml-7 px-3 py-2 rounded-md text-xs leading-relaxed italic",
                                isDark ? "bg-muted/50 text-muted-foreground" : "bg-muted/30 text-muted-foreground"
                            )}>
                                {plan.reasoning}
                            </div>
                        )}
                    </div>
                );
                continue;
            }

            if (event.type === 'searching') {
                const e = event as any;
                rows.push(
                    <div key={`searching-${i}`} className="ml-7 flex items-center gap-2 text-xs text-muted-foreground">
                        <FiBox className="h-3 w-3" />
                        <span>
                            Retrieved <span className="font-medium text-foreground">{e.result_count}</span> results in <span className="font-medium text-foreground">{e.duration_ms}ms</span>
                        </span>
                    </div>
                );
                continue;
            }

            if (event.type === 'evaluating') {
                const e = event as any;
                const eval_ = e.evaluation;
                if (eval_?.reasoning) {
                    rows.push(
                        <div key={`evaluating-${i}`}>
                            <div className={cn(
                                "ml-7 px-3 py-2 rounded-md text-xs leading-relaxed italic",
                                isDark ? "bg-muted/50 text-muted-foreground" : "bg-muted/30 text-muted-foreground"
                            )}>
                                {eval_.reasoning}
                            </div>
                        </div>
                    );
                }
                continue;
            }

            // Start of qdrant_filter (manual filter)
            if (event.type === 'operator_start' && event.op === 'qdrant_filter') {
                // Look ahead to find the filter_applied event
                let filterData = null;
                let mergeDetails: { merged?: any; existing?: any; user?: any } | null = null;
                for (let j = i + 1; j < src.length && j < i + 5; j++) {
                    if (src[j].type === 'filter_applied') {
                        filterData = (src[j] as any).filter;
                        break;
                    }
                    if (src[j].type === 'filter_merge') {
                        const e = src[j] as any;
                        mergeDetails = {
                            merged: e.merged,
                            existing: e.existing,
                            user: e.user
                        };
                        // don't break; still prefer to capture filter_applied if present
                    }
                    if (src[j].type === 'operator_end' && src[j].op === 'qdrant_filter') {
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

                // Show merge label only when both interpreted and manual filters are used
                const hasExisting = !!(mergeDetails && mergeDetails.existing && typeof mergeDetails.existing === 'object' && Object.keys(mergeDetails.existing).length > 0);
                if (hasExisting) {
                    rows.push(
                        <div key={`qdrant-${i}-merge-label`} className="px-2 py-0.5 text-[11px] opacity-70">
                            merged interpreted + manual
                        </div>
                    );
                }

                // Show the filter if we found it
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

                // Do not show merge internals; only the applied filter

                // Skip ahead to operator_end
                while (i < src.length && !(src[i].type === 'operator_end' && src[i].op === 'qdrant_filter')) {
                    i++;
                }

                if (i < src.length) {
                    rows.push(
                        <div key={`qdrant-${i}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                            Filter applied
                        </div>
                    );

                    // Add separator
                    rows.push(
                        <div key={`qdrant-${i}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );
                }
                continue;
            }

            // Start of query interpretation
            if (event.type === 'operator_start' && event.op === 'query_interpretation') {
                inInterpretation = true;
                interpretationData = {
                    reasons: [],
                    confidence: null,
                    filters: [],
                    refinedQuery: null,
                    filterApplied: null
                };
                // Show header immediately on operator start
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

            // Inside query interpretation block
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
                    // Render the aggregated interpretation block
                    const key = `interp-${i}`;

                    // Reasoning steps
                    interpretationData.reasons.forEach((reason, idx) => {
                        rows.push(
                            <div key={`${key}-reason-${idx}`} className="py-0.5 px-2 text-[11px] opacity-80">
                                {reason}
                            </div>
                        );
                    });

                    // Confidence and application state
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

                    // Proposed or applied filter JSON
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

                    // Refined query
                    if (interpretationData.refinedQuery) {
                        rows.push(
                            <div key={`${key}-refined`} className="py-0.5 px-2 text-[11px] opacity-90">
                                Refined query: {interpretationData.refinedQuery}
                            </div>
                        );
                    }

                    // End line
                    rows.push(
                        <div key={`${key}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                            Query interpretation complete
                        </div>
                    );

                    // Add separator
                    rows.push(
                        <div key={`${key}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );

                    inInterpretation = false;
                    continue;
                }

                // Skip any other events inside interpretation
                continue;
            }

            // Start of query expansion
            if (event.type === 'operator_start' && event.op === 'query_expansion') {
                inExpansion = true;
                expansionData = {
                    strategy: null,
                    reasons: [],
                    alternatives: []
                };
                // Show header immediately on operator start
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

            // Inside query expansion block
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
                    // Continue to operator_end to render
                }

                if (event.type === 'operator_end' && event.op === 'query_expansion') {
                    // Render the aggregated expansion block
                    const key = `exp-${i}`;

                    // If strategy known, show it beneath header
                    if (expansionData.strategy) {
                        rows.push(
                            <div key={`${key}-strategy`} className="py-0.5 px-2 text-[11px] opacity-80">
                                Strategy: {expansionData.strategy}
                            </div>
                        );
                    }

                    // Reasoning steps
                    expansionData.reasons.forEach((reason, idx) => {
                        rows.push(
                            <div key={`${key}-reason-${idx}`} className="py-0.5 px-2 text-[11px] opacity-80">
                                {reason}
                            </div>
                        );
                    });

                    // Generated alternatives
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

                    // End line
                    rows.push(
                        <div key={`${key}-end`} className="py-0.5 px-2 text-[11px] opacity-70">
                            Query expansion complete
                        </div>
                    );

                    // Add separator
                    rows.push(
                        <div key={`${key}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );

                    inExpansion = false;
                    continue;
                }

                // Skip any other events inside expansion
                continue;
            }

            // Start of embedding
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

            // Inside embedding block
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
                    // Continue to operator_end to render
                }

                if (event.type === 'embedding_fallback') {
                    // Handle fallback case
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
                    // Do not render a separate Embedding section; carry details to Retrieval (vector search)
                    pendingEmbedding = { ...embeddingData };
                    inEmbedding = false;
                    continue;
                }

                // Skip any other events inside embedding
                continue;
            }

            // Start of vector search
            if (event.type === 'operator_start' && event.op === 'vector_search') {
                // Simple aggregation for vector search
                const vectorSearchData = {
                    method: null as string | null,
                    finalCount: null as number | null,
                    topScores: [] as number[]
                };

                // Look ahead for vector_search events
                let j = i + 1;
                while (j < src.length && src[j].type !== 'operator_end') {
                    const nextEvent = src[j];
                    if (nextEvent.type === 'vector_search_start') {
                        vectorSearchData.method = (nextEvent as any).method;
                    } else if (nextEvent.type === 'vector_search_done') {
                        vectorSearchData.finalCount = (nextEvent as any).final_count;
                        vectorSearchData.topScores = (nextEvent as any).top_scores || [];
                    }
                    j++;
                }

                // Render the combined Retrieval block (Embedding + Vector Search)
                const key = `vector-${i}`;

                const vMethod = (vectorSearchData.method || 'hybrid') as 'hybrid' | 'neural' | 'keyword';
                const VIcon = vMethod === 'hybrid' ? FiGitMerge : vMethod === 'neural' ? FiBox : FiType;

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

                // Embedding details (if available)
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

                // Add separator
                rows.push(
                    <div key={`${key}-separator`} className="py-1">
                        <div className="mx-2 border-t border-border/30"></div>
                    </div>
                );

                // Clear carried embedding details after rendering combined block
                pendingEmbedding = null;

                // Skip to the operator_end
                while (i < src.length && !(src[i].type === 'operator_end' && src[i].op === 'vector_search')) {
                    i++;
                }
                continue;
            }

            // Start of recency bias
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

            // Inside recency block
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
                    // Handle skipped case - just show the reason
                    const reason = (event as any).reason;
                    rows.push(
                        <div key={`recency-skip-${i}`} className="py-0.5 px-2 text-[11px] opacity-90">
                            • Recency bias skipped: {reason}
                        </div>
                    );

                    // Add separator after skipped message
                    rows.push(
                        <div key={`recency-skip-${i}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );

                    // Skip to operator_end without displaying it
                    while (i < src.length && !(src[i].type === 'operator_end' && src[i].op === 'recency')) {
                        i++;
                    }

                    inRecency = false;
                    continue;
                }

                if (event.type === 'operator_end' && event.op === 'recency') {
                    // Render the aggregated recency block
                    const key = `recency-${i}`;

                    // Helper function to format time span
                    const formatTimeSpan = (seconds: number | null) => {
                        if (!seconds) return 'unknown';
                        const days = Math.floor(seconds / 86400);
                        const hours = Math.floor((seconds % 86400) / 3600);
                        const minutes = Math.floor((seconds % 3600) / 60);

                        const parts = [];
                        if (days > 0) parts.push(`${days} day${days !== 1 ? 's' : ''}`);
                        if (hours > 0) parts.push(`${hours} hour${hours !== 1 ? 's' : ''}`);
                        if (minutes > 0 && days === 0) parts.push(`${minutes} minute${minutes !== 1 ? 's' : ''}`);

                        return parts.length > 0 ? parts.join(', ') : 'less than a minute';
                    };

                    // Helper function to format date
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
                            <FiClock className="h-3 w-3 opacity-80" />
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

                    // Add separator
                    rows.push(
                        <div key={`${key}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );

                    inRecency = false;
                    continue;
                }

                // Skip any other events inside recency
                continue;
            }

            // Start of reranking
            if (event.type === 'operator_start' && event.op === 'llm_reranking') {
                inReranking = true;
                rerankingData = {
                    reasons: [],
                    rankings: [],
                    k: null
                };
                // Header
                rows.push(
                    <div key={`rerank-${i}-start`} className="px-2 py-1 text-[11px] flex items-center gap-1.5">
                        <FiList className="h-3 w-3 opacity-80" />
                        <span className="opacity-90">AI reranking</span>
                    </div>
                );
                continue;
            }

            // Inside reranking block
            if (inReranking) {
                if (event.type === 'reranking_start') {
                    const k = (event as any).k;
                    if (typeof k === 'number') {
                        rerankingData.k = k;
                        // Update the starting message with k value
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
                        // Show reasoning step immediately
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
                    // Continue to operator_end to render
                }

                if (event.type === 'operator_end' && event.op === 'llm_reranking') {
                    // Only render the final rankings summary (start and reasons already shown)
                    const key = `rerank-${i}`;

                    // Rankings
                    if (rerankingData.rankings.length > 0) {
                        rows.push(
                            <div key={`${key}-rankings-header`} className="py-0.5 px-2 text-[11px] opacity-90">
                                Reranked {rerankingData.rankings.length} result{rerankingData.rankings.length !== 1 ? 's' : ''}:
                            </div>
                        );

                        // Show top 5 rankings with scores
                        const topRankings = rerankingData.rankings.slice(0, 5);
                        topRankings.forEach((ranking, idx) => {
                            const score = typeof ranking.relevance_score === 'number'
                                ? ranking.relevance_score.toFixed(2)
                                : 'N/A';
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

                    // Add separator
                    rows.push(
                        <div key={`${key}-separator`} className="py-1">
                            <div className="mx-2 border-t border-border/30"></div>
                        </div>
                    );

                    inReranking = false;
                    continue;
                }

                // Skip any other events inside reranking
                continue;
            }

            // Skip completion-related events entirely - they're shown in SearchResponseDisplay
            if (event.type === 'completion_start' || event.type === 'completion_delta' || event.type === 'completion_done') {
                continue;
            }
            if (event.type === 'operator_start' && event.op === 'completion') {
                continue;
            }
            if (event.type === 'operator_end' && event.op === 'completion') {
                continue;
            }

            // Regular events outside interpretation, expansion, recency, and reranking
            // Special formatting for connected, start, done events
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
                // Add separator after starting search
                rows.push(
                    <div key={`${(event.seq ?? i)}-separator`} className="py-1">
                        <div className="mx-2 border-t border-border/30"></div>
                    </div>
                );
            } else if (event.type === 'done') {
                // Skip — no visual indicator for search completion
                continue;
            } else if (event.type === 'results' || event.type === 'summary') {
                // Skip results and summary events - they're shown elsewhere
                continue;
            } else if (event.type === 'error') {
                // Show error events
                const e = event as any;
                rows.push(
                    <div key={(event.seq ?? i) + "-" + i} className="py-0.5 px-2 text-[11px] text-red-400">
                        Error{e.operation ? ` in ${e.operation}` : ''}: {e.message}
                    </div>
                );
            } else {
                // Skip any other unhandled events - we only show styled events
                continue;
            }
        }

        // If interpretation never closed, still render what we have
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

        // If expansion never closed, still render what we have
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
    }, [events, isDark]);

    // Create header content with trace label and request ID
    const headerContent = (
        <>
            <span className={cn(DESIGN_SYSTEM.typography.sizes.label, "opacity-80")}>Trace</span>
            {requestId && (
                <button
                    type="button"
                    onClick={handleCopyId}
                    title="Copy Request ID"
                    className={cn(
                        "inline-flex items-center gap-1 max-w-[70%] px-1.5 py-0.5 text-[10px]",
                        DESIGN_SYSTEM.radius.button,
                        DESIGN_SYSTEM.transitions.standard,
                        isDark
                            ? "bg-gray-800/70 text-gray-300 hover:bg-gray-800 ring-1 ring-gray-800"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200 ring-1 ring-gray-200"
                    )}
                >
                    <span className="opacity-70">Request ID:</span>
                    <span className="font-mono truncate">{requestId}</span>
                    {copied ? (
                        <Check className={DESIGN_SYSTEM.icons.inline} strokeWidth={1.5} />
                    ) : (
                        <Copy className={DESIGN_SYSTEM.icons.inline} strokeWidth={1.5} />
                    )}
                </button>
            )}
        </>
    );

    // Create status ribbon
    const statusRibbon = (
        <div className="h-1.5 w-full relative overflow-hidden">
            {isLive ? (
                <>
                    <div className={cn(
                        "absolute inset-0 h-1.5 bg-gradient-to-r",
                        isDark ? "from-gray-700 to-gray-600" : "from-gray-300 to-gray-400"
                    )}></div>
                    <div className={cn(
                        "absolute inset-0 h-1.5 bg-gradient-to-r from-transparent",
                        "via-white/20 to-transparent animate-pulse"
                    )}></div>
                </>
            ) : (
                <div className={cn(
                    "absolute inset-0 h-1.5",
                    isDark ? "bg-gray-800" : "bg-gray-200"
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
            onCopy={handleCopyProcess}
            copyTooltip="Copy trace"
            autoExpandOnSearch={isSearching}
            className={className}
        >
            {/* Body - grows with content up to entities tab max height (438px) */}
            <div ref={scrollContainerRef} className={cn(
                "overflow-auto max-h-[438px]",
                DESIGN_SYSTEM.spacing.padding.compact,
                isDark ? "bg-gray-950" : "bg-white"
            )}>
                {displayRows.length === 0 ? (
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
                        {displayRows}
                        {/* Cancellation marker */}
                        {events.some((e: any) => e?.type === 'cancelled') && (
                            <div className="py-0.5 px-2 text-[11px] text-red-500">
                                Search cancelled
                            </div>
                        )}
                        {isLive && (
                            <div className="py-0.5 px-2 text-[11px] opacity-70 flex items-center gap-2">
                                <span>{isAnswering ? 'Generating answer' : 'Searching'}</span>
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
        </CollapsibleCard>
    );
};
