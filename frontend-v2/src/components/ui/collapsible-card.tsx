import { useState, useEffect, useRef, ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ChevronDown, Copy, Check } from "lucide-react";

interface CollapsibleCardProps {
  children: ReactNode;
  header: ReactNode;
  isExpanded?: boolean;
  onToggle?: (expanded: boolean) => void;
  className?: string;
  /** Copy functionality */
  onCopy?: () => Promise<void>;
  copyTooltip?: string;
  /** Auto-expand when search starts (but don't prevent manual collapse) */
  autoExpandOnSearch?: boolean;
  /** Status ribbon */
  statusRibbon?: ReactNode;
}

/**
 * Custom hook for smooth height transitions
 */
function useHeightTransition(isOpen: boolean) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number>(0);
  const [shouldRender, setShouldRender] = useState(false);
  const measureTimeoutRef = useRef<NodeJS.Timeout>(undefined);

  useEffect(() => {
    if (isOpen) {
      setShouldRender(true);
      // Measure height after render
      measureTimeoutRef.current = setTimeout(() => {
        if (containerRef.current) {
          const contentElement =
            containerRef.current.firstElementChild as HTMLElement;
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

      const contentElement =
        containerRef.current.firstElementChild as HTMLElement;
      if (contentElement) {
        resizeObserver.observe(contentElement);
      }

      return () => resizeObserver.disconnect();
    }
  }, [isOpen, shouldRender]);

  return { containerRef, height, shouldRender };
}

function CollapsibleCard({
  children,
  header,
  isExpanded: controlledExpanded,
  onToggle,
  className,
  onCopy,
  copyTooltip = "Copy",
  autoExpandOnSearch = false,
  statusRibbon,
}: CollapsibleCardProps) {
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
      console.error("Copy failed:", error);
    }
  };

  return (
    <div
      className={cn(
        "bg-card text-card-foreground overflow-hidden rounded-lg border shadow-sm",
        className
      )}
    >
      {/* Status Ribbon */}
      {statusRibbon}

      {/* Header - Always Visible */}
      <div
        className={cn(
          "flex w-full items-center justify-between px-2 py-1.5",
          "bg-muted/50 border-border/50 border-b"
        )}
      >
        {/* Header Content */}
        <div className="flex flex-1 items-center gap-2">{header}</div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          {/* Copy Button */}
          {onCopy && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 gap-1 px-1 text-xs"
              onClick={handleCopy}
              title={copyTooltip}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5" strokeWidth={1.5} />
              ) : (
                <Copy className="h-3.5 w-3.5" strokeWidth={1.5} />
              )}
              Copy
            </Button>
          )}

          {/* Collapse/Expand Button */}
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={handleToggle}
            title={isExpanded ? "Collapse" : "Expand"}
          >
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 transition-transform duration-200",
                isExpanded ? "rotate-180" : "rotate-0"
              )}
            />
          </Button>
        </div>
      </div>

      {/* Collapsible Content */}
      <div
        ref={containerRef}
        style={{
          height: `${height}px`,
          transition: "height 300ms cubic-bezier(0.4, 0, 0.2, 1)",
          overflow: "hidden",
        }}
      >
        {shouldRender && (
          <div
            className={cn(
              "transition-opacity duration-150",
              isExpanded ? "opacity-100" : "opacity-0"
            )}
          >
            {children}
          </div>
        )}
      </div>
    </div>
  );
}

export { CollapsibleCard };
export type { CollapsibleCardProps };
