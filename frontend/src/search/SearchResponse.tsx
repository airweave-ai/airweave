import React, { useState, useCallback, useMemo, useRef, useEffect, startTransition } from 'react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { Button } from '@/components/ui/button';
import {
    Layers,
    TerminalSquare,
    Clock,
    Footprints,
    Braces,
    FileJson2,
    ChevronRight,
    ChevronDown,
} from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { DESIGN_SYSTEM } from '@/lib/design-system';
import { CollapsibleCard } from '@/components/ui/CollapsibleCard';
import type { SearchEvent } from '@/search/types';
import { EntityResultCard } from './EntityResultCard';
import { StreamingSentences } from './StreamingSentences';

interface SearchResponseProps {
    searchResponse: any;
    isSearching: boolean;
    responseType?: 'raw' | 'completion';
    className?: string;
    events?: SearchEvent[];
    showTrace?: boolean;
}

// ── Trace helpers ────────────────────────────────────────────────────

const FIELD_SHORT_NAMES: Record<string, string> = {
    'airweave_system_metadata.source_name': 'source',
    'airweave_system_metadata.entity_type': 'type',
    'airweave_system_metadata.original_entity_id': 'original_id',
    'airweave_system_metadata.chunk_index': 'chunk',
    'breadcrumbs.entity_id': 'breadcrumb_id',
    'breadcrumbs.name': 'breadcrumb',
    'breadcrumbs.entity_type': 'breadcrumb_type',
};

const OP_SYMBOLS: Record<string, string> = {
    equals: '=', not_equals: '!=', contains: '~',
    greater_than: '>', less_than: '<',
    greater_than_or_equal: '>=', less_than_or_equal: '<=',
    in: 'in', not_in: 'not in',
};

function shortenField(field: string): string {
    return FIELD_SHORT_NAMES[field] || field;
}

function formatCondition(c: any): string {
    const field = shortenField(c.field || '');
    const op = OP_SYMBOLS[c.operator] || c.operator || '?';
    let val = c.value;
    if (typeof val === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(val)) {
        val = val.split('T')[0];
    }
    if (Array.isArray(val)) val = `[${val.join(', ')}]`;
    return `${field} ${op} ${val}`;
}

function formatFilterGroups(groups: any[]): string[] {
    return groups.map((g: any) =>
        (g.conditions || []).map(formatCondition).join(' AND ')
    );
}

function formatDuration(ms: number): string {
    return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

// ── Tool name labels ─────────────────────────────────────────────────

const TOOL_LABELS: Record<string, string> = {
    'search': 'Search',
    'read': 'Read',
    'add_to_results': 'Collect',
    'remove_from_results': 'Remove',
    'count': 'Count',
    'get_children': 'GetChildren',
    'get_siblings': 'GetSiblings',
    'get_parent': 'GetParent',
    'review_results': 'Review',
    'return_results_to_user': 'Return',
    'reranking': 'Rerank',
};

function formatEntityList(entities: any[], totalCount?: number, maxChars = 100): string {
    if (!entities || entities.length === 0) return '';
    const parts: string[] = [];
    let totalLen = 0;
    for (const e of entities) {
        const name = e.name?.length > 30 ? e.name.slice(0, 27) + '...' : e.name;
        const part = `${name} (${e.source_name})`;
        if (parts.length > 0 && totalLen + part.length + 2 > maxChars) break;
        parts.push(part);
        totalLen += part.length + 2; // +2 for ", "
    }
    const total = totalCount ?? entities.length;
    const remaining = total - parts.length;
    if (remaining > 0) parts.push(`+${remaining} more`);
    return parts.join(', ');
}

function getToolLabel(toolName: string, strategy?: string): string {
    if (toolName === 'search') {
        const prefix = strategy === 'keyword' ? 'Keyword'
            : strategy === 'semantic' ? 'Semantic'
                : 'Hybrid';
        return `${prefix}Search`;
    }
    return TOOL_LABELS[toolName] || toolName;
}

// ── Component ────────────────────────────────────────────────────────

export const SearchResponse: React.FC<SearchResponseProps> = ({
    searchResponse,
    isSearching,
    className,
    events = [],
    showTrace = true,
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';

    // Collapsible state with localStorage persistence
    const [isExpanded, setIsExpanded] = useState(() => {
        const stored = localStorage.getItem('searchResponse-expanded');
        return stored ? JSON.parse(stored) : true;
    });
    useEffect(() => {
        localStorage.setItem('searchResponse-expanded', JSON.stringify(isExpanded));
    }, [isExpanded]);

    // Active tab
    const [activeTab, setActiveTab] = useState<'trace' | 'entities' | 'raw'>(
        !showTrace ? 'entities' : 'entities'
    );
    const hasAutoSwitchedRef = useRef(false);

    // Pagination
    const INITIAL_RESULTS_LIMIT = 25;
    const LOAD_MORE_INCREMENT = 25;
    const [visibleResultsCount, setVisibleResultsCount] = useState(INITIAL_RESULTS_LIMIT);

    // Raw tab truncation
    const RAW_JSON_LINE_LIMIT = 500;
    const [showFullRawJson, setShowFullRawJson] = useState(false);

    // Reset on new search
    useEffect(() => {
        if (isSearching) {
            setVisibleResultsCount(INITIAL_RESULTS_LIMIT);
            setShowFullRawJson(false);
        }
    }, [isSearching]);

    // Refs
    const jsonViewerRef = useRef<HTMLDivElement>(null);
    const traceContainerRef = useRef<HTMLDivElement>(null);
    const [traceAutoScroll, setTraceAutoScroll] = useState(true);

    // Extract data from response
    const statusCode = searchResponse?.error ? (searchResponse?.status ?? 500) : 200;
    const responseTime = searchResponse?.responseTime || null;
    const results = searchResponse?.results || [];
    const hasError = Boolean(searchResponse?.error);
    const isTransientError = Boolean(searchResponse?.errorIsTransient);
    const errorDisplayMessage = isTransientError
        ? "Something went wrong, please try again."
        : searchResponse?.error;

    // Memoized style
    const syntaxStyle = useMemo(() => isDark ? materialOceanic : oneLight, [isDark]);

    // Trace scroll handling
    const handleTraceScroll = useCallback(() => {
        const el = traceContainerRef.current;
        if (!el) return;
        const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        setTraceAutoScroll(distanceFromBottom < 20);
    }, []);

    // Auto-scroll trace
    useEffect(() => {
        if (!isSearching || !traceAutoScroll) return;
        const el = traceContainerRef.current;
        if (el) el.scrollTop = el.scrollHeight;
    }, [events?.length, isSearching, traceAutoScroll]);

    // Copy handler
    const handleCopy = useCallback(async () => {
        if (activeTab === 'trace') {
            const text = traceContainerRef.current?.innerText || '';
            if (text.trim()) await navigator.clipboard.writeText(text.trim());
        } else if (activeTab === 'raw' && searchResponse) {
            await navigator.clipboard.writeText(JSON.stringify(searchResponse, null, 2));
        } else if (activeTab === 'entities' && results.length > 0) {
            await navigator.clipboard.writeText(JSON.stringify(results, null, 2));
        }
    }, [activeTab, results, searchResponse]);

    // Entity click (scroll to entity in entities tab)
    const handleEntityClick = useCallback((entityId: string) => {
        setActiveTab('entities');
        setTimeout(() => {
            const container = jsonViewerRef.current;
            if (!container) return;
            const card = container.querySelector(`[data-entity-id="${entityId}"]`) as HTMLElement;
            if (card) {
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                const origBg = card.style.backgroundColor;
                const origBorder = card.style.border;
                card.style.transition = 'all 0.3s ease';
                card.style.backgroundColor = isDark ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.15)';
                card.style.border = isDark ? '2px solid rgba(59, 130, 246, 0.5)' : '2px solid rgba(59, 130, 246, 0.4)';
                setTimeout(() => {
                    card.style.backgroundColor = origBg;
                    card.style.border = origBorder;
                }, 2000);
            }
        }, 150);
    }, [isDark]);

    // ── Expandable filters ───────────────────────────────────────────
    const [expandedFilters, setExpandedFilters] = useState<Set<number>>(new Set());
    useEffect(() => {
        if (isSearching) setExpandedFilters(new Set());
    }, [isSearching]);

    const toggleFilter = useCallback((idx: number) => {
        setExpandedFilters(prev => {
            const next = new Set(prev);
            if (next.has(idx)) next.delete(idx); else next.add(idx);
            return next;
        });
    }, []);

    // ── Trace rows ───────────────────────────────────────────────────
    const traceRows = useMemo(() => {
        const rows: React.ReactNode[] = [];

        const muted = isDark ? 'text-gray-500' : 'text-gray-400';
        const subtle = isDark ? 'text-gray-400' : 'text-gray-500';
        const thinkingBody = isDark ? 'text-gray-300' : 'text-gray-600';
        let hasEmittedFirstThinking = false;

        for (let i = 0; i < events.length; i++) {
            const event = events[i] as any;

            // ── Started ──
            if (event.type === 'started') continue;

            // ── Thinking ──
            if (event.type === 'thinking') {
                const text = event.text || event.thinking;
                const diag = event.diagnostics;
                const tokens = (diag?.prompt_tokens || diag?.completion_tokens)
                    ? `${diag.prompt_tokens.toLocaleString()}→${diag.completion_tokens.toLocaleString()} tokens`
                    : null;
                const isLatestEvent = i === events.length - 1;
                if (text || tokens) {
                    if (hasEmittedFirstThinking) {
                        rows.push(
                            <div key={`iter-sep-${i}`} className="pt-2 pb-0.5">
                                <div className={cn("border-t", isDark ? "border-gray-800/30" : "border-gray-200/40")} />
                            </div>
                        );
                    }
                    hasEmittedFirstThinking = true;
                    rows.push(
                        <div key={`thinking-${i}`} className="animate-fade-in pt-1 pb-2.5 flex gap-2">
                            <div className={cn("mt-[5px] h-1.5 w-1.5 rounded-full shrink-0", isDark ? "bg-gray-500" : "bg-gray-400")} />
                            <div className="flex-1 min-w-0">
                            <div className={cn("flex items-baseline gap-3 text-[10px] font-mono", muted)}>
                                {isLatestEvent ? (
                                    <span>Thinking</span>
                                ) : (
                                    <span>Thought for {formatDuration(event.duration_ms)}</span>
                                )}
                                {!isLatestEvent && tokens && <span className="tabular-nums">{tokens}</span>}
                            </div>
                            {text && (
                                <div className={cn("text-[10px] leading-relaxed font-mono", thinkingBody)}>
                                    <StreamingSentences
                                        text={text}
                                        animate={i === events.length - 1}
                                    />
                                </div>
                            )}
                            </div>
                        </div>
                    );
                }
                continue;
            }

            // ── Tool call ──
            if (event.type === 'tool_call') {
                const { tool_name, duration_ms, diagnostics } = event;
                const args = diagnostics?.arguments || {};
                const stats = diagnostics?.stats || {};
                const showDuration = true;

                if (tool_name === 'return_results_to_user') continue;

                const toolLabel = getToolLabel(tool_name, args.retrieval_strategy);
                const isExpanded = expandedFilters.has(i);

                // Handle errored tool calls
                if (stats.error) {
                    rows.push(
                        <div key={`tool-${i}`} className="animate-fade-in py-0.5 font-mono flex gap-2">
                            <div className={cn("mt-[5px] h-1.5 w-1.5 rounded-full shrink-0", isDark ? "bg-blue-400" : "bg-blue-500")} />
                            <div className="flex-1 min-w-0">
                            <div className="flex items-baseline gap-2 flex-wrap">
                                <span className={cn("text-[11px] font-medium", isDark ? "text-blue-400" : "text-blue-500")}>
                                    {toolLabel}
                                </span>
                                <span className={cn("text-[10px]", isDark ? "text-red-400/70" : "text-red-500/70")}>Error</span>
                                <span className={cn("text-[10px] tabular-nums opacity-60", muted)}>
                                    {formatDuration(duration_ms)}
                                </span>
                            </div>
                            {args.entity_id && (
                                <div className={cn("text-[10px]", muted)}>
                                    {args.entity_id}
                                </div>
                            )}
                            </div>
                        </div>
                    );
                    continue;
                }

                // Build headline stat and collapsed/expanded content
                let statText = '';
                const collapsedParts: string[] = [];
                const expandedLines: React.ReactNode[] = [];
                let collapsedIsOutput = false; // Whether the main collapsed line represents output
                let collapsedIsInput = false;  // Whether the main collapsed line represents input
                // Second expandable (output) — only used by search
                let outputCollapsed = '';
                const outputExpanded: React.ReactNode[] = [];

                switch (tool_name) {
                    case 'search': {
                        const query = args.query?.primary || '';
                        const variations: string[] = args.query?.variations || [];
                        const filterGroups = args.filter_groups || [];
                        const newResults = stats.new_results ?? 0;
                        const resultCount = stats.result_count ?? '?';
                        statText = newResults > 0 && newResults < resultCount
                            ? `${resultCount} results (${newResults} new)`
                            : `${resultCount} results`;

                        // Collapsed summary
                        collapsedParts.push(`"${query}"`);
                        if (variations.length > 0) collapsedParts.push(`${variations.length} variations`);
                        const totalConditions = filterGroups.reduce(
                            (sum: number, g: any) => sum + (g.conditions?.length || 0), 0
                        );
                        if (totalConditions === 1 && filterGroups.length === 1) {
                            collapsedParts.push(formatCondition(filterGroups[0].conditions[0]));
                        } else if (totalConditions > 0) {
                            collapsedParts.push(`${totalConditions} filters`);
                        }

                        // Expanded
                        expandedLines.push(<div key="query">query: "{query}"</div>);
                        if (variations.length > 0) {
                            expandedLines.push(<div key="var-header">variations:</div>);
                            variations.forEach((v: string, vi: number) => {
                                expandedLines.push(<div key={`var-${vi}`} className="ml-3">"{v}"</div>);
                            });
                        }
                        if (filterGroups.length > 0) {
                            const lines = formatFilterGroups(filterGroups);
                            expandedLines.push(<div key="filter-header">filters:</div>);
                            lines.forEach((line, fi) => {
                                expandedLines.push(
                                    <div key={`filter-${fi}`} className="ml-3">
                                        {fi > 0 && <span className="opacity-50">OR </span>}{line}
                                    </div>
                                );
                            });
                        }
                        const limitOffset = [];
                        if (args.limit) limitOffset.push(`limit: ${args.limit}`);
                        if (args.offset) limitOffset.push(`offset: ${args.offset}`);
                        if (limitOffset.length > 0) {
                            expandedLines.push(<div key="limit">{limitOffset.join('  ')}</div>);
                        }
                        // Output: first results
                        const firstResults = stats.first_results || [];
                        if (firstResults.length > 0) {
                            outputCollapsed = formatEntityList(firstResults, stats.result_count);
                            firstResults.forEach((r: any, ri: number) => {
                                outputExpanded.push(
                                    <div key={`result-${ri}`}>
                                        {r.name} <span className="opacity-50">({r.source_name} · {r.entity_type} · {r.entity_id})</span>
                                    </div>
                                );
                            });
                            if ((stats.result_count || 0) > firstResults.length) {
                                outputExpanded.push(
                                    <div key="results-more" className="opacity-50">
                                        +{stats.result_count - firstResults.length} more
                                    </div>
                                );
                            }
                        }
                        break;
                    }
                    case 'read': {
                        const readEntities = stats.entities || [];
                        statText = `${stats.found ?? '?'} entities`;
                        if (readEntities.length > 0) {
                            collapsedIsOutput = true;
                            collapsedParts.push(formatEntityList(readEntities, stats.found));
                            readEntities.forEach((r: any, ri: number) => {
                                expandedLines.push(
                                    <div key={`entity-${ri}`}>
                                        {r.name} <span className="opacity-50">({r.source_name} · {r.entity_type} · {r.entity_id})</span>
                                    </div>
                                );
                            });
                            if ((stats.found || 0) > readEntities.length) {
                                expandedLines.push(
                                    <div key="more" className="opacity-50">+{stats.found - readEntities.length} more</div>
                                );
                            }
                            if (stats.not_found > 0) {
                                expandedLines.push(<div key="notfound" className="opacity-50">{stats.not_found} not found</div>);
                            }
                        } else {
                            const ids: string[] = args.entity_ids || [];
                            if (ids.length > 0) {
                                collapsedParts.push('entity IDs');
                                expandedLines.push(<div key="ids">{ids.join(', ')}</div>);
                            }
                        }
                        break;
                    }
                    case 'add_to_results': {
                        const collectEntities = stats.entities || [];
                        const added = stats.added ?? collectEntities.length ?? '?';
                        const total = stats.total_collected ?? '?';
                        statText = `${added} added (${total} total)`;
                        if (collectEntities.length > 0) {
                            collapsedIsOutput = true;
                            collapsedParts.push(formatEntityList(collectEntities, stats.added));
                            collectEntities.forEach((r: any, ri: number) => {
                                expandedLines.push(
                                    <div key={`entity-${ri}`}>
                                        {r.name} <span className="opacity-50">({r.source_name} · {r.entity_type} · {r.entity_id})</span>
                                    </div>
                                );
                            });
                            if ((stats.added || 0) > collectEntities.length) {
                                expandedLines.push(
                                    <div key="more" className="opacity-50">+{stats.added - collectEntities.length} more</div>
                                );
                            }
                        } else {
                            const ids: string[] = args.entity_ids || [];
                            if (ids.length > 0) {
                                collapsedParts.push('entity IDs');
                                expandedLines.push(<div key="ids">{ids.join(', ')}</div>);
                            }
                        }
                        if (stats.not_found > 0) {
                            expandedLines.push(<div key="notfound" className="opacity-50">{stats.not_found} not found</div>);
                        }
                        break;
                    }
                    case 'remove_from_results': {
                        const removeEntities = stats.entities || [];
                        const ids: string[] = args.entity_ids || [];
                        statText = `${ids.length || '?'} removed (${stats.total_collected ?? '?'} total)`;
                        if (removeEntities.length > 0) {
                            collapsedIsInput = true;
                            collapsedParts.push(formatEntityList(removeEntities, args.entity_ids?.length));
                            removeEntities.forEach((r: any, ri: number) => {
                                expandedLines.push(
                                    <div key={`entity-${ri}`}>
                                        {r.name} <span className="opacity-50">({r.source_name} · {r.entity_type} · {r.entity_id})</span>
                                    </div>
                                );
                            });
                        } else if (ids.length > 0) {
                            collapsedParts.push('entity IDs');
                            expandedLines.push(<div key="ids">{ids.join(', ')}</div>);
                        }
                        break;
                    }
                    case 'count': {
                        const filterGroups = args.filter_groups || [];
                        statText = `${stats.count ?? '?'} matches`;
                        collapsedIsInput = true;
                        const totalConditions = filterGroups.reduce(
                            (sum: number, g: any) => sum + (g.conditions?.length || 0), 0
                        );
                        if (totalConditions > 0) {
                            collapsedParts.push(`${totalConditions} filter${totalConditions > 1 ? 's' : ''}`);
                        }
                        if (filterGroups.length > 0) {
                            const lines = formatFilterGroups(filterGroups);
                            lines.forEach((line, fi) => {
                                expandedLines.push(
                                    <div key={`filter-${fi}`}>
                                        {fi > 0 && <span className="opacity-50">OR </span>}{line}
                                    </div>
                                );
                            });
                        }
                        break;
                    }
                    case 'get_children':
                    case 'get_siblings': {
                        statText = `${stats.result_count ?? '?'} results`;
                        // Input: context label
                        collapsedIsInput = true;
                        collapsedParts.push(stats.context_label || `"${args.entity_id || '?'}"`);
                        // Output: entity names
                        const navResults = stats.first_results || [];
                        if (navResults.length > 0) {
                            outputCollapsed = formatEntityList(navResults, stats.result_count);
                            navResults.forEach((r: any, ri: number) => {
                                outputExpanded.push(
                                    <div key={`entity-${ri}`}>
                                        {r.name} <span className="opacity-50">({r.source_name} · {r.entity_type} · {r.entity_id})</span>
                                    </div>
                                );
                            });
                            if ((stats.result_count || 0) > navResults.length) {
                                outputExpanded.push(
                                    <div key="more" className="opacity-50">+{stats.result_count - navResults.length} more</div>
                                );
                            }
                        }
                        break;
                    }
                    case 'get_parent': {
                        statText = `${stats.found ?? stats.result_count ?? '?'} found`;
                        collapsedIsInput = true;
                        collapsedParts.push(stats.context_label || `"${args.entity_id || '?'}"`);
                        // Output: parent entity
                        const parentEntities = stats.entities || [];
                        if (parentEntities.length > 0) {
                            outputCollapsed = formatEntityList(parentEntities, stats.found);
                            parentEntities.forEach((r: any, ri: number) => {
                                outputExpanded.push(
                                    <div key={`entity-${ri}`}>
                                        {r.name} <span className="opacity-50">({r.source_name} · {r.entity_type} · {r.entity_id})</span>
                                    </div>
                                );
                            });
                        }
                        break;
                    }
                    case 'review_results': {
                        statText = `${stats.total_collected ?? '?'} collected`;
                        const reviewResults = stats.first_results || [];
                        if (reviewResults.length > 0) {
                            collapsedIsInput = true;
                            collapsedParts.push(formatEntityList(reviewResults, stats.total_collected));
                            reviewResults.forEach((r: any, ri: number) => {
                                expandedLines.push(
                                    <div key={`entity-${ri}`}>
                                        {r.name} <span className="opacity-50">({r.source_name} · {r.entity_type} · {r.entity_id})</span>
                                    </div>
                                );
                            });
                            if ((stats.total_collected || 0) > reviewResults.length) {
                                expandedLines.push(
                                    <div key="more" className="opacity-50">+{stats.total_collected - reviewResults.length} more</div>
                                );
                            }
                        }
                        break;
                    }
                }

                const collapsedSummary = collapsedParts.join('  ');
                const hasExpandable = collapsedSummary.length > 0 && expandedLines.length > 0;
                const hasBothSections = hasExpandable && outputCollapsed.length > 0;
                const collapsedLabel = (hasBothSections || collapsedIsInput) ? 'input: '
                    : collapsedIsOutput ? 'output: ' : '';

                rows.push(
                    <div key={`tool-${i}`} className="animate-fade-in py-0.5 font-mono flex gap-2">
                        <div className={cn("mt-[5px] h-1.5 w-1.5 rounded-full shrink-0", isDark ? "bg-blue-400" : "bg-blue-500")} />
                        <div className="flex-1 min-w-0">
                        {/* Headline: ToolName  stats  duration */}
                        <div className="flex items-baseline gap-2 flex-wrap">
                            <span className={cn("text-[11px] font-medium", isDark ? "text-blue-400" : "text-blue-500")}>
                                {toolLabel}
                            </span>
                            {statText && (
                                <span className={cn("text-[10px]", subtle)}>{statText}</span>
                            )}
                            {showDuration && (
                                <span className={cn("text-[10px] tabular-nums opacity-60", muted)}>
                                    {formatDuration(duration_ms)}
                                </span>
                            )}
                        </div>
                        {/* Collapsed/expanded input */}
                        {collapsedSummary && (
                            hasExpandable ? (
                                <button
                                    onClick={() => toggleFilter(i)}
                                    className={cn("flex items-center gap-0.5 text-[10px] ml-0.5", muted, "hover:underline")}
                                >
                                    {isExpanded ? <ChevronDown className="h-2.5 w-2.5" /> : <ChevronRight className="h-2.5 w-2.5" />}
                                    {collapsedLabel && <span className="opacity-50">{collapsedLabel}</span>}{collapsedSummary}
                                </button>
                            ) : (
                                <div className={cn("text-[10px] ml-3", muted)}>
                                    {collapsedLabel && <span className="opacity-50">{collapsedLabel}</span>}{collapsedSummary}
                                </div>
                            )
                        )}
                        {isExpanded && expandedLines.length > 0 && (
                            <div className={cn("text-[10px] ml-5 space-y-px", muted)}>
                                {expandedLines}
                            </div>
                        )}
                        {/* Second expandable: output (search only) */}
                        {outputCollapsed && (
                            (() => {
                                const outputKey = i + 100000;
                                const isOutputExpanded = expandedFilters.has(outputKey);
                                const hasOutputExpandable = outputExpanded.length > 0;
                                return hasOutputExpandable ? (
                                    <>
                                        <button
                                            onClick={() => toggleFilter(outputKey)}
                                            className={cn("flex items-center gap-0.5 text-[10px] ml-0.5", muted, "hover:underline")}
                                        >
                                            {isOutputExpanded ? <ChevronDown className="h-2.5 w-2.5" /> : <ChevronRight className="h-2.5 w-2.5" />}
                                            <span className="opacity-50">output: </span>{outputCollapsed}
                                        </button>
                                        {isOutputExpanded && (
                                            <div className={cn("text-[10px] ml-5 space-y-px", muted)}>
                                                {outputExpanded}
                                            </div>
                                        )}
                                    </>
                                ) : (
                                    <div className={cn("text-[10px] ml-3", muted)}><span className="opacity-50">output: </span>{outputCollapsed}</div>
                                );
                            })()
                        )}
                        </div>
                    </div>
                );
                continue;
            }

            // ── Reranking ──
            if (event.type === 'reranking') {
                const diag = event.diagnostics || {};
                const inputCount = diag.input_count ?? '?';
                const rerankResults = diag.first_results || [];
                const isRerankExpanded = expandedFilters.has(i);
                rows.push(
                    <div key={`rerank-${i}`} className="animate-fade-in py-0.5 font-mono flex gap-2">
                        <div className={cn("mt-[5px] h-1.5 w-1.5 rounded-full shrink-0", isDark ? "bg-blue-400" : "bg-blue-500")} />
                        <div className="flex-1 min-w-0">
                        <div className="flex items-baseline gap-2 flex-wrap">
                            <span className={cn("text-[11px] font-medium", isDark ? "text-blue-400" : "text-blue-500")}>
                                Rerank
                            </span>
                            <span className={cn("text-[10px]", subtle)}>{inputCount} results</span>
                            <span className={cn("text-[10px] tabular-nums opacity-60", muted)}>
                                {formatDuration(event.duration_ms)}
                            </span>
                        </div>
                        {rerankResults.length > 0 && (
                            <>
                                <button
                                    onClick={() => toggleFilter(i)}
                                    className={cn("flex items-center gap-0.5 text-[10px] ml-0.5", muted, "hover:underline")}
                                >
                                    {isRerankExpanded ? <ChevronDown className="h-2.5 w-2.5" /> : <ChevronRight className="h-2.5 w-2.5" />}
                                    <span className="opacity-50">output: </span>
                                    {rerankResults.map((r: any) =>
                                        `${r.name?.length > 20 ? r.name.slice(0, 17) + '...' : r.name} (${typeof r.relevance_score === 'number' ? r.relevance_score.toFixed(2) : '?'})`
                                    ).join(', ')}
                                </button>
                                {isRerankExpanded && (
                                    <div className={cn("text-[10px] ml-5 space-y-px", muted)}>
                                        {rerankResults.map((r: any, ri: number) => (
                                            <div key={ri}>
                                                {r.name} <span className="opacity-50">({r.source_name} · {r.entity_type} · {r.entity_id} · score: {typeof r.relevance_score === 'number' ? r.relevance_score.toFixed(3) : '?'})</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </>
                        )}
                        </div>
                    </div>
                );
                continue;
            }

            // ── Done ──
            if (event.type === 'done') {
                const diag = event.diagnostics;
                const found = diag?.all_seen_entity_ids?.length ?? 0;
                const read = diag?.all_read_entity_ids?.length ?? 0;
                const collected = diag?.all_collected_entity_ids?.length ?? 0;
                const promptTokens = diag?.prompt_tokens ?? 0;
                const completionTokens = diag?.completion_tokens ?? 0;
                const cacheRead = diag?.cache_read_input_tokens ?? 0;

                const summaryText = isDark ? 'text-gray-400' : 'text-gray-500';
                const summaryLabel = isDark ? 'text-gray-300' : 'text-gray-600';

                rows.push(
                    <div key={`done-${i}`} className={cn(
                        "mt-2 -mx-3 px-3 py-2.5 font-mono text-[10px] space-y-1 border-t",
                        isDark ? "bg-gray-900/60 border-gray-800/50" : "bg-gray-50/80 border-gray-200/50"
                    )}>
                        <div className={summaryText}>
                            <span className={summaryLabel}>{found}</span> found · <span className={summaryLabel}>{read}</span> read · <span className={summaryLabel}>{collected}</span> collected
                        </div>
                        {(promptTokens > 0 || completionTokens > 0) && (
                            <div className={summaryText}>
                                <span className={summaryLabel}>{promptTokens.toLocaleString()}</span> input · <span className={summaryLabel}>{completionTokens.toLocaleString()}</span> output tokens
                                {cacheRead > 0 && <> · <span className={summaryLabel}>{cacheRead.toLocaleString()}</span> cached</>}
                            </div>
                        )}
                        <div className={summaryText}>
                            <span className={summaryLabel}>{formatDuration(event.duration_ms)}</span> total
                        </div>
                    </div>
                );
                continue;
            }

            // ── Error ──
            if (event.type === 'error') {
                rows.push(
                    <div key={`error-${i}`} className={cn("py-0.5 text-[10px] font-mono", isDark ? "text-red-400" : "text-red-600")}>
                        Error: {event.message}
                    </div>
                );
                continue;
            }

            // ── Cancelled ──
            if ((event as any).type === 'cancelled') {
                rows.push(
                    <div key={`cancelled-${i}`} className={cn("py-0.5 text-[10px] font-mono", muted)}>
                        Cancelled
                    </div>
                );
                continue;
            }
        }

        return rows;
    }, [events, isDark, expandedFilters, toggleFilter]);

    // ── Tab switching ────────────────────────────────────────────────
    useEffect(() => {
        if (isSearching) {
            setActiveTab(showTrace ? 'trace' : 'entities');
            hasAutoSwitchedRef.current = false;
        }
    }, [isSearching, showTrace]);

    useEffect(() => {
        if (!isSearching && Array.isArray(results) && results.length > 0) {
            if (!hasAutoSwitchedRef.current) {
                setActiveTab('entities');
                hasAutoSwitchedRef.current = true;
            }
        }
    }, [isSearching, results]);

    // Guard
    if (!searchResponse && !isSearching) return null;

    // ── Header ───────────────────────────────────────────────────────
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

    const statusRibbon = (
        <div className="h-1.5 w-full relative overflow-hidden">
            {isSearching ? (
                <>
                    <div className="absolute inset-0 h-1.5 bg-gradient-to-r from-blue-500 to-indigo-500" />
                    <div className="absolute inset-0 h-1.5 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-pulse" />
                </>
            ) : (
                <div className={cn(
                    "absolute inset-0 h-1.5 bg-gradient-to-r",
                    hasError
                        ? isTransientError
                            ? "from-gray-200 to-gray-300 dark:from-gray-700 dark:to-gray-600"
                            : "from-red-500 to-red-600"
                        : "from-green-500 to-emerald-500"
                )} />
            )}
        </div>
    );

    // ── Render ────────────────────────────────────────────────────────
    return (
        <CollapsibleCard
            header={headerContent}
            statusRibbon={statusRibbon}
            isExpanded={isExpanded}
            onToggle={setIsExpanded}
            onCopy={handleCopy}
            copyTooltip={activeTab === 'trace' ? "Copy trace" : "Copy entities"}
            autoExpandOnSearch={isSearching}
            className={className}
        >
            <div className="flex flex-col">
                {/* Error Display — only for non-trace tiers (instant/classic) */}
                {hasError && !showTrace && (
                    <div className={cn(
                        "border-t p-4",
                        isTransientError
                            ? isDark ? "border-gray-800/50 bg-gray-900/40" : "border-gray-200/70 bg-gray-50"
                            : isDark ? "border-gray-800/50 bg-red-950/20" : "border-gray-200/50 bg-red-50"
                    )}>
                        <div className={cn(
                            "text-sm",
                            isTransientError
                                ? isDark ? "text-gray-100" : "text-gray-700"
                                : isDark ? "text-red-300" : "text-red-700"
                        )}>
                            {errorDisplayMessage}
                        </div>
                    </div>
                )}

                {/* Tab Navigation */}
                {(!hasError || showTrace) && (
                    <div className={cn(
                        "flex items-center border-t",
                        isDark ? "border-gray-800/50 bg-gray-900/70" : "border-gray-200/50 bg-gray-50"
                    )}>
                        {showTrace && (
                            <button
                                onClick={() => startTransition(() => setActiveTab('trace'))}
                                className={cn(
                                    "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                    activeTab === 'trace'
                                        ? isDark ? "text-white bg-gray-800/70" : "text-gray-900 bg-white"
                                        : isDark ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30" : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                                )}
                            >
                                <div className="flex items-center gap-1.5">
                                    <Footprints className="h-3 w-3" />
                                    Trace
                                </div>
                                {activeTab === 'trace' && (
                                    <div className={cn("absolute bottom-0 left-0 right-0 h-0.5", isDark ? "bg-blue-400" : "bg-blue-600")} />
                                )}
                            </button>
                        )}
                        <button
                            onClick={() => startTransition(() => setActiveTab('entities'))}
                            className={cn(
                                "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                activeTab === 'entities'
                                    ? isDark ? "text-white bg-gray-800/70" : "text-gray-900 bg-white"
                                    : isDark ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30" : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                            )}
                        >
                            <div className="flex items-center gap-1.5">
                                <FileJson2 className="h-3 w-3" strokeWidth={1.5} />
                                Entities
                            </div>
                            {activeTab === 'entities' && (
                                <div className={cn("absolute bottom-0 left-0 right-0 h-0.5", isDark ? "bg-blue-400" : "bg-blue-600")} />
                            )}
                        </button>
                        <button
                            onClick={() => startTransition(() => setActiveTab('raw'))}
                            className={cn(
                                "px-3.5 py-2 text-[13px] font-medium transition-colors relative",
                                activeTab === 'raw'
                                    ? isDark ? "text-white bg-gray-800/70" : "text-gray-900 bg-white"
                                    : isDark ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/30" : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/50"
                            )}
                        >
                            <div className="flex items-center gap-1.5">
                                <Braces className="h-3 w-3" strokeWidth={1.5} />
                                Raw
                            </div>
                            {activeTab === 'raw' && (
                                <div className={cn("absolute bottom-0 left-0 right-0 h-0.5", isDark ? "bg-blue-400" : "bg-blue-600")} />
                            )}
                        </button>
                    </div>
                )}

                {/* Tab Content */}
                {(!hasError || showTrace) && (
                    <div className={cn("border-t relative", isDark ? "border-gray-800/50" : "border-gray-200/50")}>

                        {/* ── Trace Tab ── */}
                        {showTrace && activeTab === 'trace' && (
                            <div
                                ref={traceContainerRef}
                                onScroll={handleTraceScroll}
                                className={cn(
                                    "overflow-auto max-h-[700px] raw-data-scrollbar px-3 py-2",
                                    isDark ? "bg-gray-950" : "bg-white"
                                )}
                            >
                                {events.length === 0 ? (
                                    <div className={cn("text-[10px] font-mono flex items-center")}>
                                        <span className={cn("pulse-dot", isDark ? "pulse-dot--dark" : "pulse-dot--light")} />
                                        <span className={cn("thinking-shimmer", isDark ? "thinking-shimmer--dark" : "thinking-shimmer--light")}>
                                            Thinking
                                        </span>
                                    </div>
                                ) : (
                                    <>
                                        {traceRows}
                                        {isSearching && (
                                            <div className={cn("py-1 text-[10px] font-mono flex items-center")}>
                                                <span className={cn("pulse-dot", isDark ? "pulse-dot--dark" : "pulse-dot--light")} />
                                                <span className={cn("thinking-shimmer", isDark ? "thinking-shimmer--dark" : "thinking-shimmer--light")}>
                                                    {(() => {
                                                        const last = events[events.length - 1] as any;
                                                        if (last?.type === 'thinking') return 'Searching';
                                                        if (last?.type === 'reranking') return 'Finishing';
                                                        return 'Thinking';
                                                    })()}
                                                </span>
                                            </div>
                                        )}
                                    </>
                                )}
                            </div>
                        )}

                        {/* ── Entities Tab ── */}
                        {activeTab === 'entities' && (results.length > 0 || isSearching) && (
                            <div className={cn("overflow-auto max-h-[700px] raw-data-scrollbar", isDark ? "bg-gray-900" : "bg-white")}>
                                {isSearching ? (
                                    <div className={cn(DESIGN_SYSTEM.spacing.padding.default, "animate-pulse space-y-2")}>
                                        <div className="flex gap-2">
                                            <div className="h-4 w-4 bg-gray-200 dark:bg-gray-700 rounded" />
                                            <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded" />
                                        </div>
                                        <div className="flex gap-2 ml-4">
                                            <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
                                            <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
                                        </div>
                                        <div className="flex gap-2 ml-4">
                                            <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
                                            <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded" />
                                        </div>
                                    </div>
                                ) : (
                                    <>
                                        <div ref={jsonViewerRef} className={cn("px-4 py-3 space-y-5 raw-data-scrollbar", DESIGN_SYSTEM.typography.sizes.label)}>
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
                                                        isDark ? "bg-gray-800 hover:bg-gray-700 border-gray-700 text-gray-200" : "bg-white hover:bg-gray-50 border-gray-300 text-gray-700"
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

                        {/* ── Raw Tab ── */}
                        {activeTab === 'raw' && (() => {
                            const fullJsonString = JSON.stringify(searchResponse, null, 2);
                            const jsonLines = fullJsonString.split('\n');
                            const shouldTruncate = jsonLines.length > RAW_JSON_LINE_LIMIT;
                            const displayString = showFullRawJson || !shouldTruncate
                                ? fullJsonString
                                : jsonLines.slice(0, RAW_JSON_LINE_LIMIT).join('\n') + '\n...';
                            const usePlainText = jsonLines.length > 1000;

                            return (
                                <>
                                    <div className={cn("overflow-auto max-h-[700px] raw-data-scrollbar", isDark ? "bg-gray-950" : "bg-gray-50")}>
                                        {usePlainText ? (
                                            <pre className={cn("font-mono text-[11px] p-4 m-0 leading-relaxed whitespace-pre", isDark ? "text-gray-300" : "text-gray-800")}>
                                                {displayString}
                                            </pre>
                                        ) : (
                                            <SyntaxHighlighter
                                                language="json"
                                                style={syntaxStyle}
                                                customStyle={{ margin: 0, borderRadius: 0, fontSize: '11px', padding: '1rem', background: 'transparent', lineHeight: '1.5' }}
                                                showLineNumbers={false}
                                            >
                                                {displayString}
                                            </SyntaxHighlighter>
                                        )}
                                    </div>
                                    {shouldTruncate && !showFullRawJson && (
                                        <div className={cn(
                                            "flex items-center justify-center gap-2 px-3 py-2.5 border-t",
                                            isDark ? "border-gray-800/40 bg-gray-900/30" : "border-gray-200/60 bg-gray-50/40"
                                        )}>
                                            <button
                                                onClick={() => setShowFullRawJson(true)}
                                                className={cn(
                                                    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-150",
                                                    isDark ? "text-gray-400 hover:text-gray-200 hover:bg-gray-800/50" : "text-gray-500 hover:text-gray-700 hover:bg-gray-100/80"
                                                )}
                                            >
                                                <Braces className="h-3 w-3 opacity-60" />
                                                <span>Load remaining</span>
                                                <span className="opacity-50 font-mono text-[10px]">
                                                    +{(jsonLines.length - RAW_JSON_LINE_LIMIT).toLocaleString()} lines
                                                </span>
                                            </button>
                                        </div>
                                    )}
                                </>
                            );
                        })()}
                    </div>
                )}
            </div>
        </CollapsibleCard>
    );
};
