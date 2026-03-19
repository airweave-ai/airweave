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
    Search as SearchIcon,
    BookOpen,
    PackagePlus,
    PackageMinus,
    Hash,
    FolderOpen,
    Users,
    ArrowUp,
    ClipboardList,
    ArrowDownUp,
} from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { DESIGN_SYSTEM } from '@/lib/design-system';
import { CollapsibleCard } from '@/components/ui/CollapsibleCard';
import type { SearchEvent } from '@/search/types';
import { EntityResultCard } from './EntityResultCard';

interface SearchResponseProps {
    searchResponse: any;
    isSearching: boolean;
    responseType?: 'raw' | 'completion';
    className?: string;
    events?: SearchEvent[];
    showTrace?: boolean;
}

// ── Trace helpers ────────────────────────────────────────────────────

const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

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

function getSearchLabel(strategy: string): string {
    switch (strategy) {
        case 'keyword': return 'Keyword Search';
        case 'semantic': return 'Semantic Search';
        default: return 'Hybrid Search';
    }
}

function formatDuration(ms: number): string {
    return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

// ── Tool badge config ────────────────────────────────────────────────

interface ToolBadgeConfig {
    label: string;
    icon: React.ElementType;
    dark: string;   // dark mode: bg + text + border
    light: string;  // light mode: bg + text + border
}

const TOOL_BADGES: Record<string, ToolBadgeConfig> = {
    'hybrid_search':  { label: 'Hybrid Search',  icon: SearchIcon,   dark: 'bg-blue-500/10 text-blue-400 border-blue-500/20',    light: 'bg-blue-50 text-blue-600 border-blue-200' },
    'keyword_search': { label: 'Keyword Search',  icon: SearchIcon,   dark: 'bg-blue-500/10 text-blue-400 border-blue-500/20',    light: 'bg-blue-50 text-blue-600 border-blue-200' },
    'semantic_search':{ label: 'Semantic Search', icon: SearchIcon,   dark: 'bg-blue-500/10 text-blue-400 border-blue-500/20',    light: 'bg-blue-50 text-blue-600 border-blue-200' },
    'read':           { label: 'Read',            icon: BookOpen,     dark: 'bg-amber-500/10 text-amber-400 border-amber-500/20', light: 'bg-amber-50 text-amber-600 border-amber-200' },
    'add_to_results': { label: 'Collect',         icon: PackagePlus,  dark: 'bg-green-500/10 text-green-400 border-green-500/20', light: 'bg-green-50 text-green-600 border-green-200' },
    'remove_from_results': { label: 'Remove',     icon: PackageMinus, dark: 'bg-red-500/10 text-red-400 border-red-500/20',       light: 'bg-red-50 text-red-600 border-red-200' },
    'count':          { label: 'Count',           icon: Hash,         dark: 'bg-gray-500/10 text-gray-400 border-gray-500/20',    light: 'bg-gray-100 text-gray-600 border-gray-200' },
    'get_children':   { label: 'Get Children',    icon: FolderOpen,   dark: 'bg-purple-500/10 text-purple-400 border-purple-500/20', light: 'bg-purple-50 text-purple-600 border-purple-200' },
    'get_siblings':   { label: 'Get Siblings',    icon: Users,        dark: 'bg-purple-500/10 text-purple-400 border-purple-500/20', light: 'bg-purple-50 text-purple-600 border-purple-200' },
    'get_parent':     { label: 'Get Parent',      icon: ArrowUp,      dark: 'bg-purple-500/10 text-purple-400 border-purple-500/20', light: 'bg-purple-50 text-purple-600 border-purple-200' },
    'review_results': { label: 'Review',          icon: ClipboardList,dark: 'bg-gray-500/10 text-gray-400 border-gray-500/20',    light: 'bg-gray-100 text-gray-600 border-gray-200' },
    'reranking':      { label: 'Rerank',          icon: ArrowDownUp,  dark: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20', light: 'bg-indigo-50 text-indigo-600 border-indigo-200' },
};

function getToolBadgeConfig(toolName: string, strategy?: string): ToolBadgeConfig {
    if (toolName === 'search') {
        const key = strategy === 'keyword' ? 'keyword_search'
            : strategy === 'semantic' ? 'semantic_search'
            : 'hybrid_search';
        return TOOL_BADGES[key];
    }
    return TOOL_BADGES[toolName] || {
        label: toolName, icon: SearchIcon,
        dark: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
        light: 'bg-gray-100 text-gray-600 border-gray-200',
    };
}

const ToolBadge: React.FC<{ config: ToolBadgeConfig; isDark: boolean }> = ({ config, isDark }) => {
    const Icon = config.icon;
    return (
        <span className={cn(
            "inline-flex items-center gap-0.5 px-1 py-px rounded text-[9px] font-medium border",
            isDark ? config.dark : config.light
        )}>
            <Icon className="h-2.5 w-2.5" />
            {config.label}
        </span>
    );
};

// ── Component ────────────────────────────────────────────────────────

export const SearchResponse: React.FC<SearchResponseProps> = ({
    searchResponse,
    isSearching,
    responseType = 'raw',
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

    // ── Spinner ──────────────────────────────────────────────────────
    const [spinnerFrame, setSpinnerFrame] = useState(0);
    useEffect(() => {
        if (!isSearching) return;
        const interval = setInterval(() => setSpinnerFrame(f => (f + 1) % SPINNER_FRAMES.length), 80);
        return () => clearInterval(interval);
    }, [isSearching]);

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
        const primary = isDark ? 'text-gray-200' : 'text-gray-800';
        const accent = isDark ? 'text-gray-300' : 'text-gray-600';

        for (let i = 0; i < events.length; i++) {
            const event = events[i] as any;

            // ── Started ──
            if (event.type === 'started') {
                rows.push(
                    <div key={`started-${i}`} className={cn("py-1 text-[11px]", muted)}>
                        Starting search...
                    </div>
                );
                rows.push(
                    <div key={`sep-started-${i}`} className="py-1">
                        <div className={cn("border-t", isDark ? "border-gray-800/50" : "border-gray-200/50")} />
                    </div>
                );
                continue;
            }

            // ── Thinking ──
            if (event.type === 'thinking') {
                const text = event.text || event.thinking;
                if (text) {
                    rows.push(
                        <div key={`thinking-${i}`} className={cn(
                            "animate-fade-in py-1 text-[11px] leading-relaxed italic",
                            subtle
                        )}>
                            {text}
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
                const showDuration = !['add_to_results', 'remove_from_results'].includes(tool_name);

                if (tool_name === 'return_results_to_user') continue;

                const badgeConfig = getToolBadgeConfig(tool_name, args.retrieval_strategy);

                // Build inline info (always shown next to badge)
                let statText = '';
                let inlineInfo = '';
                // Expandable content (only when there's rich detail like filters)
                let filterLines: string[] = [];
                let filterSummary = '';

                switch (tool_name) {
                    case 'search': {
                        const query = args.query?.primary || '';
                        const variations = args.query?.variations?.length || 0;
                        const filterGroups = args.filter_groups || [];
                        statText = `${stats.result_count ?? '?'} results`;
                        inlineInfo = `"${query}"`;
                        if (variations > 0) inlineInfo += ` · ${variations} var`;

                        const totalConditions = filterGroups.reduce(
                            (sum: number, g: any) => sum + (g.conditions?.length || 0), 0
                        );
                        if (totalConditions === 1 && filterGroups.length === 1) {
                            inlineInfo += ` · ${formatCondition(filterGroups[0].conditions[0])}`;
                        } else if (totalConditions > 0) {
                            filterSummary = `${totalConditions} filter${totalConditions > 1 ? 's' : ''}`;
                            filterLines = formatFilterGroups(filterGroups);
                        }
                        break;
                    }
                    case 'read':
                        statText = `${stats.found ?? '?'}/${args.entity_ids?.length || '?'} found`;
                        break;
                    case 'add_to_results':
                        statText = `${args.entity_ids?.length || stats.total_collected || '?'}`;
                        break;
                    case 'remove_from_results':
                        statText = `${args.entity_ids?.length || '?'}`;
                        break;
                    case 'count':
                        statText = `${stats.count ?? '?'} matches`;
                        break;
                    case 'get_children':
                    case 'get_siblings':
                    case 'get_parent':
                        statText = `${stats.result_count ?? '?'} results`;
                        inlineInfo = `"${args.entity_id || '?'}"`;
                        break;
                    case 'review_results':
                        statText = `${stats.total_collected ?? '?'} collected`;
                        break;
                }

                const isExpanded = expandedFilters.has(i);
                const hasExpandable = filterLines.length > 0;

                rows.push(
                    <div key={`tool-${i}`} className="animate-fade-in py-0.5">
                        {/* Badge + inline info + stats + duration */}
                        <div className="flex items-center gap-1.5 flex-wrap">
                            <ToolBadge config={badgeConfig} isDark={isDark} />
                            {inlineInfo && <span className={cn("text-[10px]", subtle)}>{inlineInfo}</span>}
                            {(statText || showDuration) && (
                                <span className={cn("text-[10px] tabular-nums", muted)}>
                                    {[statText, showDuration ? formatDuration(duration_ms) : ''].filter(Boolean).join(' · ')}
                                </span>
                            )}
                        </div>
                        {/* Expandable filters (only when there are multi-condition filters) */}
                        {hasExpandable && (
                            <>
                                <button
                                    onClick={() => toggleFilter(i)}
                                    className={cn("flex items-center gap-0.5 text-[10px] mt-0.5 ml-0.5", subtle, "hover:underline")}
                                >
                                    {isExpanded ? <ChevronDown className="h-2.5 w-2.5" /> : <ChevronRight className="h-2.5 w-2.5" />}
                                    {filterSummary}
                                </button>
                                {isExpanded && (
                                    <div className={cn("text-[10px] mt-0.5 ml-4 space-y-0.5", subtle)}>
                                        {filterLines.map((line, idx) => (
                                            <div key={idx}>
                                                {idx > 0 && <span className={muted}>OR </span>}
                                                {line}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                );
                continue;
            }

            // ── Reranking ──
            if (event.type === 'reranking') {
                const inputCount = event.diagnostics?.input_count ?? '?';
                const rerankBadge = TOOL_BADGES['reranking'];
                rows.push(
                    <div key={`rerank-${i}`} className="animate-fade-in py-1">
                        <div className="flex items-center gap-2">
                            <ToolBadge config={rerankBadge} isDark={isDark} />
                            <span className={cn("text-[10px] tabular-nums", muted)}>
                                {inputCount} results · {formatDuration(event.duration_ms)}
                            </span>
                        </div>
                    </div>
                );
                continue;
            }

            // ── Done ──
            if (event.type === 'done') {
                const diag = event.diagnostics;
                const resultCount = event.results?.length ?? 0;
                const seen = diag?.all_seen_entity_ids?.length ?? 0;
                const read = diag?.all_read_entity_ids?.length ?? 0;
                const collected = diag?.all_collected_entity_ids?.length ?? 0;
                const promptTokens = diag?.prompt_tokens ?? 0;
                const completionTokens = diag?.completion_tokens ?? 0;

                rows.push(
                    <div key={`done-sep-${i}`} className="py-1.5">
                        <div className={cn("border-t", isDark ? "border-gray-800/50" : "border-gray-200/50")} />
                    </div>
                );
                rows.push(
                    <div key={`done-${i}`} className={cn("text-[10px] space-y-0.5", accent)}>
                        <div>{resultCount} results · {seen} seen · {read} read · {collected} collected</div>
                        {(promptTokens > 0 || completionTokens > 0) && (
                            <div>{promptTokens.toLocaleString()} prompt tokens · {completionTokens.toLocaleString()} completion tokens</div>
                        )}
                        <div>Total: {formatDuration(event.duration_ms)}</div>
                    </div>
                );
                continue;
            }

            // ── Error ──
            if (event.type === 'error') {
                rows.push(
                    <div key={`error-${i}`} className="py-0.5 text-[11px] text-red-400">
                        Error: {event.message}
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
                {/* Error Display */}
                {hasError && (
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
                {!hasError && (
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
                {!hasError && (
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
                                    <div className={cn("text-[11px] font-mono", isDark ? "text-gray-500" : "text-gray-400")}>
                                        {SPINNER_FRAMES[spinnerFrame]}
                                    </div>
                                ) : (
                                    <>
                                        {traceRows}
                                        {isSearching && (
                                            <div className={cn("py-1 text-[11px] font-mono", isDark ? "text-gray-500" : "text-gray-400")}>
                                                {SPINNER_FRAMES[spinnerFrame]}
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
