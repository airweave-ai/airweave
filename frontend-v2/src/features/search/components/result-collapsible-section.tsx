/**
 * ResultCollapsibleSection - Collapsible section with chevron toggle
 */

import { Check, ChevronDown, ChevronRight, Copy } from "lucide-react";
import { useState } from "react";

interface ResultCollapsibleSectionProps {
  title: string;
  count?: number;
  children: React.ReactNode;
  defaultExpanded?: boolean;
  showCopyButton?: boolean;
  copyText?: string;
}

export function ResultCollapsibleSection({
  title,
  count,
  children,
  defaultExpanded = false,
  showCopyButton = false,
  copyText,
}: ResultCollapsibleSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!copyText) return;

    try {
      await navigator.clipboard.writeText(copyText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error("Failed to copy:", error);
    }
  };

  return (
    <div className="border-t">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="text-muted-foreground hover:text-foreground hover:bg-muted/50 flex w-full items-center gap-2 px-4 py-2 text-[10px] font-semibold tracking-wider uppercase transition-all duration-200"
      >
        {isExpanded ? (
          <ChevronDown className="size-3" />
        ) : (
          <ChevronRight className="size-3" />
        )}
        {title}
        {count !== undefined && ` (${count})`}
      </button>

      {isExpanded && (
        <div className="relative px-4 pb-3">
          {showCopyButton && copyText && (
            <button
              onClick={handleCopy}
              className="text-muted-foreground hover:text-foreground hover:bg-muted absolute top-0 right-4 z-10 rounded-lg p-1.5 transition-all duration-200"
              title="Copy content"
            >
              {copied ? (
                <Check className="size-3.5" />
              ) : (
                <Copy className="size-3.5" />
              )}
            </button>
          )}
          {children}
        </div>
      )}
    </div>
  );
}
