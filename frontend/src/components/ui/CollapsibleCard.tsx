import React, { useState, useEffect, useRef, ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { Button } from '@/components/ui/button';
import { ChevronDown, Copy, Check } from 'lucide-react';
import { DESIGN_SYSTEM } from '@/lib/design-system';

interface CollapsibleCardProps {
    children: ReactNode;
    header: ReactNode;
    isExpanded?: boolean;
    onToggle?: (expanded: boolean) => void;
    className?: string;
    // Copy functionality
    onCopy?: () => Promise<void>;
    copyTooltip?: string;
    // Auto-expand when search starts (but don't prevent manual collapse)
    autoExpandOnSearch?: boolean;
    // Status ribbon
    statusRibbon?: ReactNode;
}

// Custom hook for smooth height transitions (based on EntityStateList)
const useHeightTransition = (isOpen: boolean) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [height, setHeight] = useState<number>(0);
    const [shouldRender, setShouldRender] = useState(false);
    const measureTimeoutRef = useRef<NodeJS.Timeout>();

    useEffect(() => {
        if (isOpen) {
            setShouldRender(true);
            // Measure height after render
            measureTimeoutRef.current = setTimeout(() => {
                if (containerRef.current) {
                    const contentElement = containerRef.current.firstElementChild as HTMLElement;
                    if (contentElement) {
                        const newHeight = contentElement.scrollHeight;
                        setHeight(newHeight);
                    }
                }
            }, 10);
        } else {
            setHeight(0);
            // Delay unmounting to allow close animation
            const timer = setTimeout(() => setShouldRender(false), 300);
            return () => clearTimeout(timer);
        }

        return () => {
            if (measureTimeoutRef.current) {
                clearTimeout(measureTimeoutRef.current);
            }
        };
    }, [isOpen]);

    // Re-measure on content changes
    useEffect(() => {
        if (isOpen && shouldRender && containerRef.current) {
            const resizeObserver = new ResizeObserver((entries) => {
                for (const entry of entries) {
                    const newHeight = entry.contentRect.height;
                    if (newHeight > 0) {
                        setHeight(newHeight);
                    }
                }
            });

            const contentElement = containerRef.current.firstElementChild as HTMLElement;
            if (contentElement) {
                resizeObserver.observe(contentElement);
            }

            return () => resizeObserver.disconnect();
        }
    }, [isOpen, shouldRender]);

    return { containerRef, height, shouldRender };
};

export const CollapsibleCard: React.FC<CollapsibleCardProps> = ({
    children,
    header,
    isExpanded: controlledExpanded,
    onToggle,
    className,
    onCopy,
    copyTooltip = "Copy",
    autoExpandOnSearch = false,
    statusRibbon
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';

    // Internal state for uncontrolled mode
    const [internalExpanded, setInternalExpanded] = useState(true);
    const [copied, setCopied] = useState(false);

    // Determine if controlled or uncontrolled
    const isControlled = controlledExpanded !== undefined;
    const isExpanded = isControlled ? controlledExpanded : internalExpanded;

    // Auto-expand when search starts (if enabled)
    useEffect(() => {
        if (autoExpandOnSearch) {
            if (isControlled) {
                onToggle?.(true);
            } else {
                setInternalExpanded(true);
            }
        }
    }, [autoExpandOnSearch, isControlled, onToggle]);

    // Height transition hook
    const { containerRef, height, shouldRender } = useHeightTransition(isExpanded);

    const handleToggle = () => {
        const newExpanded = !isExpanded;

        if (isControlled) {
            onToggle?.(newExpanded);
        } else {
            setInternalExpanded(newExpanded);
        }
    };

    const handleCopy = async () => {
        if (!onCopy) return;

        try {
            await onCopy();
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (error) {
            console.error('Copy failed:', error);
        }
    };

    return (
        <div className={cn(
            DESIGN_SYSTEM.radius.card,
            DESIGN_SYSTEM.shadows.card,
            "overflow-hidden",
            isDark ? "bg-gray-950 ring-1 ring-gray-800" : "bg-white ring-1 ring-gray-200",
            className
        )}>
            {/* Status Ribbon */}
            {statusRibbon}

            {/* Header - Always Visible */}
            <div className={cn(
                "w-full py-1.5 px-2",
                isDark ? "bg-gray-900/60 border-b border-gray-800/50" : "bg-gray-50/80 border-b border-gray-200/50",
                "flex items-center justify-between"
            )}>
                {/* Header Content */}
                <div className="flex items-center gap-2 flex-1">
                    {header}
                </div>

                {/* Controls */}
                <div className={cn("flex items-center", DESIGN_SYSTEM.spacing.gaps.standard)}>
                    {/* Copy Button */}
                    {onCopy && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className={cn(
                                DESIGN_SYSTEM.typography.sizes.label,
                                "gap-1 px-1",
                                DESIGN_SYSTEM.buttons.heights.compact
                            )}
                            onClick={handleCopy}
                            title={copyTooltip}
                        >
                            {copied ? <Check className={DESIGN_SYSTEM.icons.inline} strokeWidth={1.5} /> : <Copy className={DESIGN_SYSTEM.icons.inline} strokeWidth={1.5} />}
                            Copy
                        </Button>
                    )}

                    {/* Collapse/Expand Button */}
                    <Button
                        variant="ghost"
                        size="icon"
                        className={cn(
                            DESIGN_SYSTEM.buttons.heights.compact,
                            "w-6"
                        )}
                        onClick={handleToggle}
                        title={isExpanded ? "Collapse" : "Expand"}
                    >
                        <ChevronDown className={cn(
                            DESIGN_SYSTEM.icons.inline,
                            DESIGN_SYSTEM.transitions.standard,
                            isExpanded ? "rotate-180" : "rotate-0"
                        )} />
                    </Button>
                </div>
            </div>

            {/* Collapsible Content */}
            <div
                ref={containerRef}
                style={{
                    height: `${height}px`,
                    transition: 'height 300ms cubic-bezier(0.4, 0, 0.2, 1)',
                    overflow: 'hidden'
                }}
            >
                {shouldRender && (
                    <div className={cn(
                        DESIGN_SYSTEM.transitions.fast,
                        isExpanded ? "opacity-100" : "opacity-0"
                    )}>
                        {children}
                    </div>
                )}
            </div>
        </div>
    );
};
