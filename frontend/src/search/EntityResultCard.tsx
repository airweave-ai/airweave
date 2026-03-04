import React, { useState, useMemo, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight, ExternalLink, Copy, Check, Link as LinkIcon, Clock } from 'lucide-react';
import { getAppIconUrl } from '@/lib/utils/icons';
import { useTheme } from '@/lib/theme-provider';

// Module-level cache for lazily-loaded heavy dependencies.
// Loaded once on first content expand, then reused across all cards.
let _markdownModule: { default: React.ComponentType<any> } | null = null;
let _remarkGfm: any = null;
let _syntaxHighlighter: React.ComponentType<any> | null = null;
let _styles: { materialOceanic: any; oneLight: any } | null = null;
let _loadingPromise: Promise<void> | null = null;

function loadHeavyDeps(): Promise<void> {
    if (_markdownModule && _remarkGfm && _syntaxHighlighter && _styles) {
        return Promise.resolve();
    }
    if (!_loadingPromise) {
        _loadingPromise = Promise.all([
            import('react-markdown').then(m => { _markdownModule = m; }),
            import('remark-gfm').then(m => { _remarkGfm = m.default; }),
            import('react-syntax-highlighter').then(m => { _syntaxHighlighter = m.Prism; }),
            import('react-syntax-highlighter/dist/esm/styles/prism').then(m => {
                _styles = { materialOceanic: m.materialOceanic, oneLight: m.oneLight };
            }),
        ]).then(() => {});
    }
    return _loadingPromise;
}
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface EntityResultCardProps {
    result: any;
    index: number;
    isDark: boolean;
    onEntityIdClick?: (entityId: string) => void;
}

// Comparison function for React.memo
const arePropsEqual = (prevProps: EntityResultCardProps, nextProps: EntityResultCardProps) => {
    return (
        prevProps.index === nextProps.index &&
        prevProps.isDark === nextProps.isDark &&
        prevProps.result.id === nextProps.result.id &&
        prevProps.result.score === nextProps.result.score
    );
};

// NOTE: formatEmbeddableText removed - textual_representation is already
// properly formatted by entity_pipeline.py, no need to reformat

/**
 * EntityResultCard - A human-readable card view for entity search results
 */
const EntityResultCardComponent: React.FC<EntityResultCardProps> = ({
    result,
    index,
    isDark,
    onEntityIdClick
}) => {
    const [isPropertiesExpanded, setIsPropertiesExpanded] = useState(false);
    const [isPreviewExpanded, setIsPreviewExpanded] = useState(false); // Collapsed by default for performance
    const [isMetadataExpanded, setIsMetadataExpanded] = useState(false);
    const [isContentExpanded, setIsContentExpanded] = useState(false);
    const [isRawExpanded, setIsRawExpanded] = useState(false);
    const [copiedField, setCopiedField] = useState<string | null>(null);
    const [expandedFields, setExpandedFields] = useState<Set<string>>(new Set());
    const { resolvedTheme } = useTheme();

    // Track whether heavy deps are loaded (triggers re-render when they arrive)
    const [depsReady, setDepsReady] = useState(!!_markdownModule);
    const needsDeps = isContentExpanded || isRawExpanded || isPreviewExpanded;

    useEffect(() => {
        if (needsDeps && !depsReady) {
            loadHeavyDeps().then(() => setDepsReady(true));
        }
    }, [needsDeps, depsReady]);

    const ReactMarkdown = _markdownModule?.default ?? null;
    const SyntaxHighlighter = _syntaxHighlighter;
    const remarkGfmPlugin = _remarkGfm;

    const score = result.score;

    const sourceFields = result.source_fields || {};

    // Determine if score looks like cosine similarity (0-1 range) or something else
    const isNormalizedScore = score !== undefined && score >= 0 && score <= 1;

    // Format score for display
    const getScoreDisplay = () => {
        if (score === undefined) return null;

        // For scores in 0-1 range (cosine similarity), show as percentage
        if (isNormalizedScore) {
            return {
                value: `${(score * 100).toFixed(1)}%`,
                color: score >= 0.7 ? 'green' : score >= 0.5 ? 'yellow' : 'gray'
            };
        }

        // For other scores (e.g., BM25), show raw value
        return {
            value: score.toFixed(3),
            color: score >= 10 ? 'green' : score >= 5 ? 'yellow' : 'gray'
        };
    };

    const scoreDisplay = getScoreDisplay();

    // Extract key fields — handle both regular (system_metadata) and agentic (airweave_system_metadata) shapes
    const entityId = result.entity_id;
    const sysMetadata = result.system_metadata || result.airweave_system_metadata || {};
    const sourceName = sysMetadata.source_name || 'Unknown Source';
    const sourceIconUrl = getAppIconUrl(sourceName, resolvedTheme);
    const textualRepresentation = result.textual_representation || '';
    const breadcrumbs = result.breadcrumbs || [];
    // URL fields may be in source_fields (regular) or at top level (agentic)
    const webUrl = sourceFields.web_url || result.web_url;
    const url = sourceFields.url || result.url;
    const openUrl = webUrl || url;
    const hasDownloadUrl = Boolean(url && webUrl && url !== webUrl);

    // Use textual_representation directly - it's already formatted by entity_pipeline.py
    const formattedContent = useMemo(() => {
        return textualRepresentation;
    }, [textualRepresentation]);

    // Extract title and metadata from flat result structure
    const title = result.name || 'Untitled';
    const escapeRegex = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const rawEntityType = sysMetadata.entity_type || '';
    let entityTypeCore = rawEntityType.replace(/Entity$/, '');
    if (entityTypeCore && sourceName) {
        const normalizedSource = sourceName.replace(/[\s_-]/g, '');
        if (normalizedSource) {
            const prefixRegex = new RegExp(`^${escapeRegex(normalizedSource)}`, 'i');
            const condensedEntity = entityTypeCore.replace(/[\s_-]/g, '');
            if (prefixRegex.test(condensedEntity)) {
                entityTypeCore = entityTypeCore.slice(normalizedSource.length);
            }
        }
    }
    const entityType = entityTypeCore
        ? entityTypeCore.replace(/([A-Z])/g, ' $1').trim() || 'Document'
        : 'Document';
    const context = breadcrumbs.length > 0 ? breadcrumbs.map((b: any) =>
        typeof b === 'string' ? b : b.name || ''
    ).filter(Boolean).join(' > ') : '';

    // Extract the most relevant timestamp (updated_at, fallback to created_at)
    const relevantTimestamp = result.updated_at || result.created_at;

    // Get Airweave logo for section headers
    const airweaveLogo = isDark
        ? '/airweave-logo-svg-white-darkbg.svg'
        : '/airweave-logo-svg-lightbg-blacklogo.svg';

    // Format source name (capitalize first letter of each word)
    const formattedSourceName = sourceName
        .split('_')
        .map((word: string) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');

    // Extract metadata from source_fields (source-specific fields)
    const metadata = useMemo(() => {
        const filtered: Record<string, any> = {};
        const excludeKeys = [
            'url', 'web_url',  // Already displayed as links
            'textual_representation',  // Already displayed in preview
            'vector', 'vectors'
        ];

        Object.entries(sourceFields).forEach(([key, value]) => {
            if (!excludeKeys.includes(key) && value !== null && value !== undefined && value !== '') {
                // Format key names nicely
                const formattedKey = key
                    .split('_')
                    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                    .join(' ');
                filtered[formattedKey] = value;
            }
        });

        return filtered;
    }, [sourceFields]);

    const hasMetadata = Object.keys(metadata).length > 0;

    // Prioritize important fields and limit display
    const IMPORTANT_FIELDS = ['Owner', 'Assignee', 'Status', 'Priority', 'Due Date', 'Author', 'Completion', 'Tags', 'Labels'];
    const MAX_FIELDS_DEFAULT = 4; // Show max 4 fields by default

    const { importantMetadata, remainingMetadata } = useMemo(() => {
        const important: Record<string, any> = {};
        const remaining: Record<string, any> = {};

        // First, collect important fields
        Object.entries(metadata).forEach(([key, value]) => {
            if (IMPORTANT_FIELDS.some(field => key.toLowerCase().includes(field.toLowerCase()))) {
                important[key] = value;
            } else {
                remaining[key] = value;
            }
        });

        // If we have fewer than MAX_FIELDS_DEFAULT important fields, add some remaining ones
        const importantCount = Object.keys(important).length;
        if (importantCount < MAX_FIELDS_DEFAULT) {
            const remainingEntries = Object.entries(remaining);
            const toAdd = remainingEntries.slice(0, MAX_FIELDS_DEFAULT - importantCount);
            toAdd.forEach(([key, value]) => {
                important[key] = value;
                delete remaining[key];
            });
        }

        return { importantMetadata: important, remainingMetadata: remaining };
    }, [metadata]);

    const hasRemainingMetadata = Object.keys(remainingMetadata).length > 0;

    // Copy to clipboard handler
    const handleCopy = async (text: string, fieldName: string) => {
        try {
            await navigator.clipboard.writeText(text);
            setCopiedField(fieldName);
            setTimeout(() => setCopiedField(null), 2000);
        } catch (error) {
            console.error('Failed to copy:', error);
        }
    };

    // Toggle field expansion
    const toggleFieldExpansion = (fieldKey: string) => {
        setExpandedFields(prev => {
            const newSet = new Set(prev);
            if (newSet.has(fieldKey)) {
                newSet.delete(fieldKey);
            } else {
                newSet.add(fieldKey);
            }
            return newSet;
        });
    };

    // Format date/timestamp values
    const formatDate = (dateString: string): string => {
        try {
            const date = new Date(dateString);
            if (isNaN(date.getTime())) {
                return dateString; // Not a valid date
            }

            // Format as: "Jan 5, 2025 at 12:17 PM"
            const formatted = date.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
            }) + ' at ' + date.toLocaleTimeString('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });

            // Add relative time for recent dates
            const now = new Date();
            const diffMs = now.getTime() - date.getTime();
            const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

            if (diffDays === 0) {
                return `Today at ${date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })}`;
            } else if (diffDays === 1) {
                return `Yesterday at ${date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })}`;
            } else if (diffDays < 7) {
                return `${diffDays} days ago`;
            }

            return formatted;
        } catch (error) {
            return dateString;
        }
    };

    // Check if a value is a date/timestamp
    const isDateField = (key: string, value: any): boolean => {
        if (typeof value !== 'string') return false;

        // Check if field name suggests it's a date
        const dateFieldPatterns = ['date', 'time', 'created', 'updated', 'modified', 'deleted', 'scheduled'];
        const lowerKey = key.toLowerCase();
        if (!dateFieldPatterns.some(pattern => lowerKey.includes(pattern))) {
            return false;
        }

        // Check if value matches ISO date format
        const isoDateRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/;
        return isoDateRegex.test(value);
    };

    // Format and truncate field value
    const formatFieldValue = (value: any, key: string, maxLength: number = 150) => {
        let stringValue: string;

        // Check if it's a date field and format it nicely
        if (isDateField(key, value)) {
            stringValue = formatDate(value);
        } else if (typeof value === 'object' && value !== null) {
            stringValue = JSON.stringify(value, null, 2);
        } else {
            stringValue = String(value);
        }

        const isExpanded = expandedFields.has(key);
        const needsTruncation = stringValue.length > maxLength;

        if (!needsTruncation) {
            return { displayValue: stringValue, needsTruncation: false, isDate: isDateField(key, value) };
        }

        if (isExpanded) {
            return { displayValue: stringValue, needsTruncation: true, isDate: isDateField(key, value) };
        }

        return {
            displayValue: stringValue.substring(0, maxLength) + '...',
            needsTruncation: true,
            isDate: isDateField(key, value)
        };
    };

    const syntaxStyle = useMemo(
        () => _styles ? (isDark ? _styles.materialOceanic : _styles.oneLight) : {},
        [isDark, depsReady]
    );

    return (
        <div
            data-entity-id={entityId}
            className={cn(
                "group relative rounded-xl transition-all duration-300 overflow-hidden raw-data-scrollbar",
                isDark
                    ? "bg-gradient-to-br from-gray-900/90 to-gray-900/50 border border-gray-800/60"
                    : "bg-white border border-gray-200/80",
                "backdrop-blur-sm"
            )}
        >
            {/* Header Section */}
            <div className={cn(
                "px-4 py-3",
                isDark ? "border-b border-gray-800/50" : "border-b border-gray-100"
            )}>
                <div className="flex items-start justify-between gap-3">
                    {/* Title with Icon */}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-start gap-2.5">
                            {/* Source Icon */}
                            <div
                                className={cn(
                                    "flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center overflow-hidden",
                                    isDark ? "bg-gray-800/50" : "bg-gray-50"
                                )}
                                title={formattedSourceName}
                            >
                                <img
                                    src={sourceIconUrl}
                                    alt={formattedSourceName}
                                    className="w-full h-full object-contain p-1.5"
                                    onError={(e) => {
                                        e.currentTarget.style.display = 'none';
                                    }}
                                />
                            </div>
                            <div className="flex-1 min-w-0 pt-0.5">
                                <div className="flex flex-wrap items-center gap-2 mb-1.5">
                                    <h3 className={cn(
                                        "text-[14px] font-semibold break-words leading-snug tracking-tight",
                                        isDark ? "text-gray-50" : "text-gray-900"
                                    )}>
                                        {title}
                                    </h3>
                                    {openUrl && (
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <a
                                                href={openUrl}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className={cn(
                                                    "inline-flex items-center gap-1.5 text-[12px] font-medium transition-all duration-200 hover:gap-2",
                                                    isDark
                                                        ? "text-blue-400 hover:text-blue-300"
                                                        : "text-blue-600 hover:text-blue-700"
                                                )}
                                            >
                                                <ExternalLink className="h-3 w-3" />
                                                Open in {formattedSourceName}
                                            </a>
                                            {hasDownloadUrl && (
                                                <a
                                                    href={url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className={cn(
                                                        "inline-flex items-center gap-1 text-[11px] font-medium transition-all duration-200 hover:gap-1.5",
                                                        isDark
                                                            ? "text-blue-400 hover:text-blue-300"
                                                            : "text-blue-600 hover:text-blue-700"
                                                    )}
                                                >
                                                    <LinkIcon className="h-3 w-3" />
                                                    Download original
                                                </a>
                                            )}
                                        </div>
                                    )}
                                </div>

                                {/* Context and Type */}
                                <div className="flex flex-wrap items-center gap-1 mb-0">


                                    <span className={cn(
                                        "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium",
                                        isDark
                                            ? "bg-gray-800/60 text-gray-200 border border-gray-700/50"
                                            : "bg-gray-100 text-gray-700 border border-gray-200/60"
                                    )}>
                                        {entityType}
                                    </span>
                                    {context && context.length > 0 && (
                                        <span className={cn(
                                            "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium",
                                            isDark
                                                ? "bg-gray-800/60 text-gray-300 border border-gray-700/50"
                                                : "bg-gray-50 text-gray-600 border border-gray-200/60"
                                        )}>
                                            {context}
                                        </span>
                                    )}

                                    {/* Last Updated Timestamp */}
                                    {relevantTimestamp && (
                                        <TooltipProvider delayDuration={200}>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <span className={cn(
                                                        "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium cursor-help",
                                                        isDark
                                                            ? "bg-gray-800/40 text-gray-400 border border-gray-700/40"
                                                            : "bg-gray-50/60 text-gray-600 border border-gray-200/50"
                                                    )}>
                                                        <Clock className="h-3 w-3" strokeWidth={1.5} />
                                                        {formatDate(relevantTimestamp)}
                                                    </span>
                                                </TooltipTrigger>
                                                <TooltipContent
                                                    side="top"
                                                    className={cn(
                                                        "px-3 py-2 max-w-[280px] backdrop-blur-sm",
                                                        isDark
                                                            ? "bg-gray-900/95 border border-gray-700/50 shadow-xl"
                                                            : "bg-white/95 border border-gray-200 shadow-lg"
                                                    )}
                                                >
                                                    <div className="space-y-1">
                                                        <div className={cn(
                                                            "text-[11px] font-bold tracking-wide",
                                                            isDark ? "text-gray-300" : "text-gray-700"
                                                        )}>
                                                            {result.updated_at ? 'Last Updated' : 'Created'}
                                                        </div>
                                                        <div className={cn(
                                                            "text-[12px] font-mono",
                                                            isDark ? "text-gray-400" : "text-gray-600"
                                                        )}>
                                                            {new Date(relevantTimestamp).toLocaleString('en-US', {
                                                                year: 'numeric',
                                                                month: 'short',
                                                                day: 'numeric',
                                                                hour: '2-digit',
                                                                minute: '2-digit',
                                                                second: '2-digit',
                                                                hour12: true
                                                            })}
                                                        </div>
                                                    </div>
                                                </TooltipContent>
                                            </Tooltip>
                                        </TooltipProvider>
                                    )}
                                </div>

                            </div>
                        </div>
                    </div>

                    {/* Unified badge: Result number + Score */}
                    {scoreDisplay && (
                        <TooltipProvider delayDuration={200}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <div
                                        className={cn(
                                            "flex-shrink-0 flex items-center gap-2 px-3 py-1 rounded-full text-[11px] font-semibold whitespace-nowrap transition-all duration-200 cursor-help shadow-sm hover:shadow-md",
                                            // Green for high scores - vibrant and clean
                                            scoreDisplay.color === 'green' && (
                                                isDark
                                                    ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20"
                                                    : "bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100"
                                            ),
                                            // Yellow for medium scores - warm and inviting
                                            scoreDisplay.color === 'yellow' && (
                                                isDark
                                                    ? "bg-amber-500/15 text-amber-400 border border-amber-500/30 hover:bg-amber-500/20"
                                                    : "bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100"
                                            ),
                                            // Gray for low scores - subtle and professional
                                            scoreDisplay.color === 'gray' && (
                                                isDark
                                                    ? "bg-gray-700/40 text-gray-400 border border-gray-600/50 hover:bg-gray-700/50"
                                                    : "bg-gray-100 text-gray-600 border border-gray-300 hover:bg-gray-150"
                                            )
                                        )}
                                    >
                                        {/* Result number */}
                                        <span className="font-bold tracking-wider opacity-70">#{index + 1}</span>

                                        {/* Divider */}
                                        <div className={cn(
                                            "w-px h-3 opacity-30",
                                            isDark ? "bg-gray-400" : "bg-gray-600"
                                        )} />

                                        {/* Score */}
                                        <span className="font-mono tracking-tight">{scoreDisplay.value}</span>
                                    </div>
                                </TooltipTrigger>
                                <TooltipContent
                                    side="left"
                                    className={cn(
                                        "px-3 py-2.5 max-w-[280px] backdrop-blur-sm",
                                        isDark
                                            ? "bg-gray-900/95 border border-gray-700/50 shadow-xl"
                                            : "bg-white/95 border border-gray-200 shadow-lg"
                                    )}
                                >
                                    <div className="space-y-2">
                                        {/* Result number */}
                                        <div className={cn(
                                            "text-[11px] font-bold tracking-wide",
                                            isDark ? "text-gray-300" : "text-gray-700"
                                        )}>
                                            Result #{index + 1}
                                        </div>

                                        {/* Similarity score */}
                                        <div className={cn(
                                            "text-[12px]",
                                            isDark ? "text-gray-400" : "text-gray-600"
                                        )}>
                                            <span className="font-medium">Similarity:</span>{' '}
                                            <span className="font-semibold">
                                                {isNormalizedScore
                                                    ? `${(score * 100).toFixed(1)}%`
                                                    : score.toFixed(3)
                                                }
                                            </span>
                                        </div>

                                        {/* Divider */}
                                        <div className={cn(
                                            "h-px w-full",
                                            isDark ? "bg-gray-700/50" : "bg-gray-200"
                                        )} />

                                        {/* Explanation */}
                                        <div className={cn(
                                            "text-[11px] leading-relaxed",
                                            isDark ? "text-gray-500" : "text-gray-500"
                                        )}>
                                            Position determined by semantic reranking to maximize topical relevance.
                                        </div>
                                    </div>
                                </TooltipContent>
                            </Tooltip>
                        </TooltipProvider>
                    )}
                </div>
            </div>

            {/* Main Content - Formatted embeddable text - Collapsible */}
            {formattedContent && (
                <div className={cn(
                    "border-t",
                    isDark ? "border-gray-800/50" : "border-gray-100"
                )}>
                    {/* Section Header - Clickable */}
                    <button
                        onClick={() => setIsPreviewExpanded(!isPreviewExpanded)}
                        className={cn(
                            "w-full px-4 py-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider transition-all duration-200",
                            isDark
                                ? "text-gray-500 hover:text-gray-400 hover:bg-gray-900/30"
                                : "text-gray-500 hover:text-gray-600 hover:bg-gray-50/50"
                        )}
                    >
                        {isPreviewExpanded ? (
                            <ChevronDown className="h-3 w-3" />
                        ) : (
                            <ChevronRight className="h-3 w-3" />
                        )}
                        {/* Airweave Icon */}
                        <div className="w-3.5 h-3.5 rounded-sm overflow-hidden flex items-center justify-center flex-shrink-0 opacity-60">
                            <img
                                src={airweaveLogo}
                                alt="Airweave"
                                className="w-full h-full object-contain"
                            />
                        </div>
                        Preview
                    </button>

                    {isPreviewExpanded && (
                        <div className={cn(
                            "px-4 pb-3",
                            isDark ? "text-gray-200" : "text-gray-800"
                        )}>
                            <div className="relative">
                                <button
                                    onClick={() => handleCopy(formattedContent, 'content')}
                                    className={cn(
                                        "absolute top-0 right-0 p-1.5 rounded-lg transition-all duration-200 z-10",
                                        isDark
                                            ? "hover:bg-gray-800/80 text-gray-400 hover:text-gray-300"
                                            : "hover:bg-gray-100 text-gray-600 hover:text-gray-700"
                                    )}
                                    title="Copy content"
                                >
                                    {copiedField === 'content' ? (
                                        <Check className="h-3.5 w-3.5" />
                                    ) : (
                                        <Copy className="h-3.5 w-3.5" />
                                    )}
                                </button>

                                {/* Container for content with truncation */}
                                <div className="relative">
                                    <div className={cn(
                                        !isContentExpanded && formattedContent.length > 500 && "max-h-[200px] overflow-hidden"
                                    )}>
                                        {ReactMarkdown ? (
                                            <ReactMarkdown
                                                remarkPlugins={remarkGfmPlugin ? [remarkGfmPlugin] : []}
                                                components={{
                                                    h1: ({ node, ...props }) => <h1 className="text-base font-bold mt-4 mb-2 first:mt-0" {...props} />,
                                                    h2: ({ node, ...props }) => <h2 className="text-sm font-bold mt-3 mb-2 first:mt-0" {...props} />,
                                                    h3: ({ node, ...props }) => <h3 className="text-sm font-semibold mt-3 mb-1.5 first:mt-0" {...props} />,
                                                    p: ({ node, ...props }) => <p className="text-[13px] leading-relaxed mb-2" {...props} />,
                                                    ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-2 space-y-1 text-[13px]" {...props} />,
                                                    ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-2 space-y-1 text-[13px]" {...props} />,
                                                    li: ({ node, ...props }) => <li className="text-[13px] leading-relaxed" {...props} />,
                                                    blockquote: ({ node, ...props }) => (
                                                        <blockquote className={cn(
                                                            "border-l-4 pl-3 my-2 italic text-[13px]",
                                                            isDark ? "border-gray-600 text-gray-400" : "border-gray-300 text-gray-600"
                                                        )} {...props} />
                                                    ),
                                                    code(props) {
                                                        const { children, className, node, ...rest } = props;
                                                        const match = /language-(\w+)/.exec(className || '');
                                                        return match && SyntaxHighlighter ? (
                                                            <SyntaxHighlighter
                                                                language={match[1]}
                                                                style={syntaxStyle}
                                                                customStyle={{
                                                                    margin: '0.5rem 0',
                                                                    borderRadius: '0.375rem',
                                                                    fontSize: '0.75rem',
                                                                    padding: '0.75rem',
                                                                    background: isDark ? 'rgba(17, 24, 39, 0.8)' : 'rgba(249, 250, 251, 0.95)'
                                                                }}
                                                            >
                                                                {String(children).replace(/\n$/, '')}
                                                            </SyntaxHighlighter>
                                                        ) : (
                                                            <code className={cn(
                                                                "px-1.5 py-0.5 rounded text-[11px] font-mono",
                                                                isDark
                                                                    ? "bg-gray-800 text-gray-300"
                                                                    : "bg-gray-100 text-gray-800"
                                                            )} {...rest}>
                                                                {children}
                                                            </code>
                                                        );
                                                    },
                                                    strong: ({ node, ...props }) => <strong className="font-semibold" {...props} />,
                                                    em: ({ node, ...props }) => <em className="italic" {...props} />,
                                                }}
                                            >
                                                {formattedContent}
                                            </ReactMarkdown>
                                        ) : (
                                            <div className="text-[13px] whitespace-pre-wrap opacity-70">
                                                {formattedContent.slice(0, 500)}{formattedContent.length > 500 ? '...' : ''}
                                            </div>
                                        )}
                                    </div>

                                    {/* Fade overlay when content is truncated */}
                                    {!isContentExpanded && formattedContent.length > 500 && (
                                        <div className={cn(
                                            "absolute bottom-0 left-0 right-0 h-16 pointer-events-none",
                                            isDark
                                                ? "bg-gradient-to-t from-gray-900 to-transparent"
                                                : "bg-gradient-to-t from-white to-transparent"
                                        )} />
                                    )}
                                </div>

                                {/* Show More/Less button for long content */}
                                {formattedContent.length > 500 && (
                                    <button
                                        onClick={() => setIsContentExpanded(!isContentExpanded)}
                                        className={cn(
                                            "mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all duration-200",
                                            isDark
                                                ? "text-blue-400 hover:text-blue-300 bg-blue-950/30 hover:bg-blue-950/50 border border-blue-900/50"
                                                : "text-blue-600 hover:text-blue-700 bg-blue-50/50 hover:bg-blue-50 border border-blue-200/60"
                                        )}
                                    >
                                        {isContentExpanded ? (
                                            <>
                                                <ChevronDown className="h-3.5 w-3.5" />
                                                Show Less
                                            </>
                                        ) : (
                                            <>
                                                <ChevronRight className="h-3.5 w-3.5" />
                                                Show Full Content
                                            </>
                                        )}
                                    </button>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Important Metadata Fields - Collapsible */}
            {Object.keys(importantMetadata).length > 0 && (
                <div className={cn(
                    "border-t",
                    isDark ? "border-gray-800/50" : "border-gray-100"
                )}>
                    {/* Section Header - Clickable */}
                    <button
                        onClick={() => setIsPropertiesExpanded(!isPropertiesExpanded)}
                        className={cn(
                            "w-full px-4 py-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider transition-all duration-200",
                            isDark
                                ? "text-gray-500 hover:text-gray-400 hover:bg-gray-900/30"
                                : "text-gray-500 hover:text-gray-600 hover:bg-gray-50/50"
                        )}
                    >
                        {isPropertiesExpanded ? (
                            <ChevronDown className="h-3 w-3" />
                        ) : (
                            <ChevronRight className="h-3 w-3" />
                        )}
                        {/* Airweave Icon */}
                        <div className="w-3.5 h-3.5 rounded-sm overflow-hidden flex items-center justify-center flex-shrink-0 opacity-60">
                            <img
                                src={airweaveLogo}
                                alt="Airweave"
                                className="w-full h-full object-contain"
                            />
                        </div>
                        Properties
                    </button>

                    {isPropertiesExpanded && (
                        <div className={cn(
                            "px-4 pb-2.5",
                            isDark ? "bg-gray-900/20" : "bg-gray-50/50"
                        )}>
                            <div className="grid grid-cols-2 gap-x-6 gap-y-2.5">
                                {Object.entries(importantMetadata).map(([key, value]) => {
                                    const { displayValue, needsTruncation, isDate } = formatFieldValue(value, key);
                                    const isExpanded = expandedFields.has(key);

                                    return (
                                        <div key={key} className="flex flex-col gap-1">
                                            <div className="flex items-start gap-2.5">
                                                <span className={cn(
                                                    "text-[10px] font-semibold uppercase tracking-wider min-w-[80px] pt-0.5",
                                                    isDark ? "text-gray-500" : "text-gray-500"
                                                )}>
                                                    {key}
                                                </span>
                                                <span className={cn(
                                                    "text-[12px] break-words flex-1 leading-snug",
                                                    isDate && "inline-flex items-center gap-1.5",
                                                    isDark ? "text-gray-300" : "text-gray-700"
                                                )}>
                                                    {isDate && <Clock className="h-3 w-3 opacity-60 flex-shrink-0" />}
                                                    {displayValue}
                                                </span>
                                            </div>
                                            {needsTruncation && (
                                                <button
                                                    onClick={() => toggleFieldExpansion(key)}
                                                    className={cn(
                                                        "text-[10px] font-medium self-start ml-[80px] transition-all duration-200 hover:translate-x-0.5",
                                                        isDark
                                                            ? "text-blue-400 hover:text-blue-300"
                                                            : "text-blue-600 hover:text-blue-700"
                                                    )}
                                                >
                                                    {isExpanded ? '← Show Less' : 'Show More →'}
                                                </button>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Show More/Less Button for Additional Metadata */}
                            {hasRemainingMetadata && (
                                <>
                                    <button
                                        onClick={() => setIsMetadataExpanded(!isMetadataExpanded)}
                                        className={cn(
                                            "mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all duration-200",
                                            isDark
                                                ? "text-blue-400 hover:text-blue-300 bg-blue-950/30 hover:bg-blue-950/50 border border-blue-900/50"
                                                : "text-blue-600 hover:text-blue-700 bg-blue-50/50 hover:bg-blue-50 border border-blue-200/60"
                                        )}
                                    >
                                        {isMetadataExpanded ? (
                                            <>
                                                <ChevronDown className="h-3.5 w-3.5" />
                                                Show Less
                                            </>
                                        ) : (
                                            <>
                                                <ChevronRight className="h-3.5 w-3.5" />
                                                {Object.keys(remainingMetadata).length} More Field{Object.keys(remainingMetadata).length !== 1 ? 's' : ''}
                                            </>
                                        )}
                                    </button>

                                    {/* Additional Metadata - Collapsible */}
                                    {isMetadataExpanded && (
                                        <div className={cn(
                                            "grid grid-cols-2 gap-x-6 gap-y-2.5 mt-3 pt-3",
                                            isDark ? "border-t border-gray-800/50" : "border-t border-gray-200/50"
                                        )}>
                                            {Object.entries(remainingMetadata).map(([key, value]) => {
                                                const { displayValue, needsTruncation, isDate } = formatFieldValue(value, key);
                                                const isExpanded = expandedFields.has(key);

                                                return (
                                                    <div key={key} className="flex flex-col gap-1">
                                                        <div className="flex items-start gap-2.5">
                                                            <span className={cn(
                                                                "text-[10px] font-semibold uppercase tracking-wider min-w-[80px] pt-0.5",
                                                                isDark ? "text-gray-500" : "text-gray-500"
                                                            )}>
                                                                {key}
                                                            </span>
                                                            <span className={cn(
                                                                "text-[12px] break-words flex-1 leading-snug",
                                                                isDate && "inline-flex items-center gap-1.5",
                                                                isDark ? "text-gray-300" : "text-gray-700"
                                                            )}>
                                                                {isDate && <Clock className="h-3 w-3 opacity-60 flex-shrink-0" />}
                                                                {displayValue}
                                                            </span>
                                                        </div>
                                                        {needsTruncation && (
                                                            <button
                                                                onClick={() => toggleFieldExpansion(key)}
                                                                className={cn(
                                                                    "text-[10px] font-medium self-start ml-[80px] transition-all duration-200 hover:translate-x-0.5",
                                                                    isDark
                                                                        ? "text-blue-400 hover:text-blue-300"
                                                                        : "text-blue-600 hover:text-blue-700"
                                                                )}
                                                            >
                                                                {isExpanded ? '← Show Less' : 'Show More →'}
                                                            </button>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Raw JSON View - Collapsible (for debugging) */}
            <div className={cn(
                "border-t",
                isDark ? "border-gray-800/50" : "border-gray-100"
            )}>
                <button
                    onClick={() => setIsRawExpanded(!isRawExpanded)}
                    className={cn(
                        "w-full px-4 py-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider transition-all duration-200",
                        isDark
                            ? "text-gray-500 hover:text-gray-400 hover:bg-gray-900/30"
                            : "text-gray-500 hover:text-gray-600 hover:bg-gray-50/50"
                    )}
                >
                    {isRawExpanded ? (
                        <ChevronDown className="h-3 w-3" />
                    ) : (
                        <ChevronRight className="h-3 w-3" />
                    )}
                    {/* Airweave Icon */}
                    <div className="w-3.5 h-3.5 rounded-sm overflow-hidden flex items-center justify-center flex-shrink-0 opacity-60">
                        <img
                            src={airweaveLogo}
                            alt="Airweave"
                            className="w-full h-full object-contain"
                        />
                    </div>
                    View Raw Data
                </button>

                {isRawExpanded && (
                    <div className="px-4 pb-3">
                        {/* Copy button header - outside scrollable area */}
                        <div className={cn(
                            "flex items-center justify-end px-3 py-2 rounded-t-lg border-b",
                            isDark
                                ? "bg-gray-900/40 border-gray-800/60"
                                : "bg-gray-50/80 border-gray-200/60"
                        )}>
                            <button
                                onClick={() => handleCopy(JSON.stringify(result, null, 2), 'raw')}
                                className={cn(
                                    "flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium transition-all duration-200",
                                    isDark
                                        ? "hover:bg-gray-800 text-gray-400 hover:text-gray-300"
                                        : "hover:bg-gray-100 text-gray-600 hover:text-gray-700"
                                )}
                            >
                                {copiedField === 'raw' ? (
                                    <>
                                        <Check className="h-3 w-3" />
                                        <span>Copied!</span>
                                    </>
                                ) : (
                                    <>
                                        <Copy className="h-3 w-3" />
                                        <span>Copy</span>
                                    </>
                                )}
                            </button>
                        </div>
                        {/* Scrollable code area with custom scrollbar */}
                        <div className={cn(
                            "rounded-b-lg overflow-hidden",
                            // Custom scrollbar styles
                            "raw-data-scrollbar"
                        )}>
                            {SyntaxHighlighter ? (
                                <SyntaxHighlighter
                                    language="json"
                                    style={syntaxStyle}
                                    customStyle={{
                                        margin: 0,
                                        borderRadius: 0,
                                        fontSize: '0.65rem',
                                        padding: '0.75rem',
                                        background: 'transparent',
                                        backgroundColor: 'transparent',
                                        maxHeight: '300px',
                                        overflow: 'auto',
                                        border: 'none',
                                        boxShadow: 'none',
                                        outline: 'none'
                                    }}
                                    showLineNumbers={false}
                                    wrapLines={false}
                                    lineProps={{ style: { backgroundColor: 'transparent', background: 'transparent' } }}
                                    codeTagProps={{ style: { backgroundColor: 'transparent', background: 'transparent' } }}
                                    PreTag={({ children, ...props }) => (
                                        <pre {...props} style={{ ...props.style, background: 'transparent', backgroundColor: 'transparent', margin: 0, padding: 0 }}>
                                            {children}
                                        </pre>
                                    )}
                                >
                                    {JSON.stringify(result, null, 2)}
                                </SyntaxHighlighter>
                            ) : (
                                <pre className="text-[0.65rem] p-3 font-mono opacity-70 max-h-[300px] overflow-auto">
                                    {JSON.stringify(result, null, 2)}
                                </pre>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

// Export memoized version for better performance
export const EntityResultCard = React.memo(EntityResultCardComponent, arePropsEqual);
