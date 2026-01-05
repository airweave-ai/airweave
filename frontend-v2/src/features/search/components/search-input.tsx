/**
 * SearchInput - Textarea input for search queries with usage limit display
 */

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface UsageLimitInfo {
  isChecking: boolean;
  isAllowed: boolean;
  reason?: "usage_limit_exceeded" | "payment_required" | "no_sources" | string;
}

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  isDisabled: boolean;
  isSearching: boolean;
  usageLimit?: UsageLimitInfo;
}

export function SearchInput({
  value,
  onChange,
  onSubmit,
  isDisabled,
  isSearching,
  usageLimit,
}: SearchInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isDisabled && !isSearching && value.trim()) {
        onSubmit();
      }
    }
  };

  if (isDisabled && usageLimit) {
    // For "no_sources", show the message as placeholder text without tooltip
    if (usageLimit.reason === "no_sources") {
      return (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
            }
          }}
          placeholder="Connect a source to start searching"
          disabled
          className="placeholder:text-muted-foreground h-20 w-full resize-none overflow-y-auto rounded-xl bg-transparent px-2 py-1.5 pr-28 text-sm leading-relaxed opacity-60 outline-none"
        />
      );
    }

    // For other reasons (usage limits, payment issues), show tooltip with details
    return (
      <TooltipProvider delayDuration={0}>
        <Tooltip>
          <TooltipTrigger asChild>
            <div>
              <textarea
                value={value}
                onChange={(e) => onChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                  }
                }}
                placeholder="Ask a question about your data"
                disabled
                className="placeholder:text-muted-foreground h-20 w-full resize-none overflow-y-auto rounded-xl bg-transparent px-2 py-1.5 pr-28 text-sm leading-relaxed opacity-60 outline-none"
              />
            </div>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            <p className="text-sm">
              {usageLimit.isChecking ? (
                "Checking usage..."
              ) : usageLimit.reason === "usage_limit_exceeded" ? (
                <>
                  Query limit reached.{" "}
                  <a
                    href="/organization/settings?tab=billing"
                    className="underline"
                  >
                    Upgrade your plan
                  </a>{" "}
                  to continue searching.
                </>
              ) : usageLimit.reason === "payment_required" ? (
                <>
                  Billing issue detected.{" "}
                  <a
                    href="/organization/settings?tab=billing"
                    className="underline"
                  >
                    Update billing
                  </a>{" "}
                  to continue searching.
                </>
              ) : (
                "Search is currently disabled."
              )}
            </p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={handleKeyDown}
      placeholder="Ask a question about your data"
      className="placeholder:text-muted-foreground h-20 w-full resize-none overflow-y-auto rounded-xl bg-transparent px-2 py-1.5 pr-28 text-sm leading-relaxed outline-none"
    />
  );
}
