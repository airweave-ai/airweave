/**
 * SearchSubmitButton - Submit/cancel/retry button for search
 */

import { ArrowUp, RefreshCw, Square } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface SearchSubmitButtonProps {
  isSearching: boolean;
  hasQuery: boolean;
  queriesAllowed: boolean;
  isCheckingUsage: boolean;
  canRetry: boolean;
  retryMessage?: string | null;
  onSubmit: () => void;
  onCancel: () => void;
  onRetry: () => void;
}

export function SearchSubmitButton({
  isSearching,
  hasQuery,
  queriesAllowed,
  isCheckingUsage,
  canRetry,
  retryMessage,
  onSubmit,
  onCancel,
  onRetry,
}: SearchSubmitButtonProps) {
  const handleClick = () => {
    if (isSearching) {
      onCancel();
    } else if (canRetry) {
      onRetry();
    } else {
      onSubmit();
    }
  };

  const getTooltipText = () => {
    if (isSearching) return "Stop search";
    if (canRetry)
      return retryMessage || "Connection interrupted. Click to retry.";
    if (!hasQuery) return "Type a question to enable";
    if (!queriesAllowed) return "Query limit reached";
    if (isCheckingUsage) return "Checking usage...";
    return "Send query";
  };

  const getIcon = () => {
    if (isSearching) {
      return <Square className="size-4 text-red-500" />;
    }
    if (canRetry) {
      return <RefreshCw className="text-muted-foreground size-4" />;
    }
    return <ArrowUp className="size-4" />;
  };

  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            size="icon"
            className="size-8"
            onClick={handleClick}
            disabled={
              isSearching
                ? false
                : !hasQuery || !queriesAllowed || isCheckingUsage
            }
          >
            {getIcon()}
          </Button>
        </TooltipTrigger>
        <TooltipContent>{getTooltipText()}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
