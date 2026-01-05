/**
 * SearchResponse - Display search results and completion
 *
 * Features:
 * - Markdown rendering with code syntax highlighting
 * - Entity citation links [[N]] in answers
 * - Raw JSON view tab
 * - Response time display
 * - Trace view for search operations
 * - LocalStorage persistence for UI state
 */

import {
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Loader2,
  SearchX,
} from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useLocalStorageState } from "@/hooks/use-local-storage-state";
import { cn } from "@/lib/utils";

import type {
  SearchEvent,
  SearchResponse as SearchResponseType,
} from "../types";
import { formatResponseTime, parseMarkdownContent } from "../utils/markdown";
import { EntityResultCard } from "./entity-result-card";
import { SearchTrace } from "./search-trace";

// Types
interface SearchResponseProps {
  searchResponse: SearchResponseType | null;
  isSearching: boolean;
  responseType?: "raw" | "completion";
  events?: SearchEvent[];
  className?: string;
}

type TabType = "trace" | "answer" | "entities" | "raw";

// LocalStorage keys
const STORAGE_KEYS = {
  EXPANDED: "searchResponse-expanded",
  ACTIVE_TAB: "searchResponse-activeTab",
  TRACE_EXPANDED: "searchTrace-expanded",
};

export function SearchResponse({
  searchResponse,
  isSearching,
  responseType = "raw",
  events = [],
  className,
}: SearchResponseProps) {
  // Copy state
  const [copiedCompletion, setCopiedCompletion] = useState(false);
  const [copiedRawJson, setCopiedRawJson] = useState(false);

  // Persisted UI state
  const defaultTab: TabType =
    responseType === "completion" ? "answer" : "entities";
  const [activeTab, setActiveTab] = useLocalStorageState<TabType>(
    STORAGE_KEYS.ACTIVE_TAB,
    defaultTab
  );
  const [isExpanded, setIsExpanded] = useLocalStorageState(
    STORAGE_KEYS.EXPANDED,
    true
  );

  // Pagination state
  const INITIAL_RESULTS_LIMIT = 25;
  const LOAD_MORE_INCREMENT = 25;
  const [visibleResultsCount, setVisibleResultsCount] = useState(
    INITIAL_RESULTS_LIMIT
  );

  // Raw JSON view state
  const RAW_JSON_LINE_LIMIT = 500;
  const [showFullRawJson, setShowFullRawJson] = useState(false);

  // Entity refs for scrolling
  const entityRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Extract data from response - memoize results to avoid re-creating array reference
  const completion = searchResponse?.completion || "";
  const results = useMemo(
    () => (searchResponse?.results || []) as Record<string, unknown>[],
    [searchResponse?.results]
  );
  const responseTime = searchResponse?.responseTime;
  const hasError = Boolean(searchResponse?.error);
  const isTransientError = Boolean(searchResponse?.errorIsTransient);
  const errorDisplayMessage = isTransientError
    ? "Something went wrong, please try again."
    : searchResponse?.error;

  // Handle scrolling to entity
  const scrollToEntity = useCallback(
    (index: number) => {
      const ref = entityRefs.current.get(index);
      if (ref) {
        ref.scrollIntoView({ behavior: "smooth", block: "center" });
        // Flash highlight
        ref.classList.add("ring-2", "ring-blue-500");
        setTimeout(() => {
          ref.classList.remove("ring-2", "ring-blue-500");
        }, 1500);
      }
      // Switch to entities tab if not there
      setActiveTab("entities");
    },
    [setActiveTab]
  );

  // Handle copy completion
  const handleCopyCompletion = useCallback(async () => {
    if (completion) {
      await navigator.clipboard.writeText(completion);
      setCopiedCompletion(true);
      setTimeout(() => setCopiedCompletion(false), 2000);
    }
  }, [completion]);

  // Handle copy raw JSON
  const handleCopyRawJson = useCallback(async () => {
    if (searchResponse) {
      await navigator.clipboard.writeText(
        JSON.stringify(searchResponse, null, 2)
      );
      setCopiedRawJson(true);
      setTimeout(() => setCopiedRawJson(false), 2000);
    }
  }, [searchResponse]);

  // Raw JSON content
  const rawJsonContent = useMemo(() => {
    if (!searchResponse) return "";
    const fullJson = JSON.stringify(searchResponse, null, 2);
    const lines = fullJson.split("\n");
    if (!showFullRawJson && lines.length > RAW_JSON_LINE_LIMIT) {
      return lines.slice(0, RAW_JSON_LINE_LIMIT).join("\n") + "\n// ...";
    }
    return fullJson;
  }, [searchResponse, showFullRawJson]);

  const rawJsonLineCount = useMemo(() => {
    if (!searchResponse) return 0;
    return JSON.stringify(searchResponse, null, 2).split("\n").length;
  }, [searchResponse]);

  // Visible results for pagination
  const visibleResults = useMemo(
    () => results.slice(0, visibleResultsCount),
    [results, visibleResultsCount]
  );

  const hasMoreResults = results.length > visibleResultsCount;
  const hasTrace = events.length > 0;

  // Rendered markdown content
  const renderedCompletion = useMemo(() => {
    if (!completion) return null;
    return parseMarkdownContent(completion, scrollToEntity);
  }, [completion, scrollToEntity]);

  // Don't render if no search response and not searching
  if (!searchResponse && !isSearching) {
    return null;
  }

  // Loading state
  if (isSearching && !searchResponse) {
    return (
      <div className={cn("bg-card mt-4 rounded-lg border p-6", className)}>
        <div className="flex items-center justify-center gap-2">
          <Loader2 className="size-4 animate-spin" />
          <span className="text-muted-foreground text-sm">Searching...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (hasError) {
    return (
      <div
        className={cn(
          "border-destructive/50 bg-destructive/10 mt-4 rounded-lg border p-6",
          className
        )}
      >
        <p className="text-destructive text-sm">{errorDisplayMessage}</p>
      </div>
    );
  }

  // Empty state
  if (results.length === 0 && !completion) {
    return (
      <EmptyState
        icon={<SearchX />}
        title="No results found"
        description="Try adjusting your search query"
        className={cn("bg-card mt-4 rounded-lg border", className)}
      />
    );
  }

  return (
    <div className={cn("mt-4 space-y-4", className)}>
      {/* Header with tabs and response time */}
      <div className="flex items-center justify-between">
        {/* Tab Buttons */}
        <div className="flex gap-2">
          {hasTrace && (
            <Button
              variant={activeTab === "trace" ? "default" : "outline"}
              size="sm"
              onClick={() => setActiveTab("trace")}
            >
              Trace
            </Button>
          )}
          {completion && (
            <Button
              variant={activeTab === "answer" ? "default" : "outline"}
              size="sm"
              onClick={() => setActiveTab("answer")}
            >
              Answer
            </Button>
          )}
          <Button
            variant={activeTab === "entities" ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveTab("entities")}
          >
            Results ({results.length})
          </Button>
          <Button
            variant={activeTab === "raw" ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveTab("raw")}
          >
            Raw
          </Button>
        </div>

        {/* Response time and collapse */}
        <div className="flex items-center gap-3">
          {responseTime && (
            <span className="text-muted-foreground text-xs">
              {formatResponseTime(responseTime)}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="size-8 p-0"
          >
            {isExpanded ? (
              <ChevronUp className="size-4" />
            ) : (
              <ChevronDown className="size-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Collapsible content */}
      {isExpanded && (
        <>
          {/* Trace Tab */}
          {activeTab === "trace" && hasTrace && (
            <SearchTrace
              events={events}
              isSearching={isSearching}
              className="bg-card rounded-lg border"
            />
          )}

          {/* Answer Tab */}
          {activeTab === "answer" && completion && (
            <div className="bg-card rounded-lg border p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold">AI-Generated Answer</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyCompletion}
                  className="size-8 p-0"
                >
                  {copiedCompletion ? (
                    <Check className="size-4 text-green-500" />
                  ) : (
                    <Copy className="size-4" />
                  )}
                </Button>
              </div>
              <div className="prose prose-sm dark:prose-invert max-w-none text-sm leading-relaxed">
                {renderedCompletion}
              </div>
            </div>
          )}

          {/* Entities Tab */}
          {activeTab === "entities" && results.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">
                  {results.length} Result{results.length !== 1 ? "s" : ""}
                </h3>
              </div>

              <div className="space-y-3">
                {visibleResults.map((result, index) => (
                  <div
                    key={
                      (result.id as string) ||
                      (result.entity_id as string) ||
                      index
                    }
                    ref={(el) => {
                      if (el) {
                        entityRefs.current.set(index, el);
                      }
                    }}
                    data-entity-index={index}
                    className="transition-all duration-200"
                  >
                    <EntityResultCard result={result} index={index} />
                  </div>
                ))}
              </div>

              {/* Load More Button */}
              {hasMoreResults && (
                <div className="flex justify-center pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setVisibleResultsCount(
                        (prev) => prev + LOAD_MORE_INCREMENT
                      )
                    }
                  >
                    Load{" "}
                    {Math.min(
                      LOAD_MORE_INCREMENT,
                      results.length - visibleResultsCount
                    )}{" "}
                    More
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Raw JSON Tab */}
          {activeTab === "raw" && searchResponse && (
            <div className="bg-card rounded-lg border">
              <div className="flex items-center justify-between border-b px-4 py-2">
                <span className="text-muted-foreground text-xs">
                  {rawJsonLineCount} lines
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyRawJson}
                  className="size-8 p-0"
                >
                  {copiedRawJson ? (
                    <Check className="size-4 text-green-500" />
                  ) : (
                    <Copy className="size-4" />
                  )}
                </Button>
              </div>
              <div className="max-h-[500px] overflow-auto bg-slate-900 p-4">
                <pre className="text-xs text-slate-300">
                  <code>{rawJsonContent}</code>
                </pre>
              </div>
              {rawJsonLineCount > RAW_JSON_LINE_LIMIT && !showFullRawJson && (
                <div className="border-t px-4 py-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowFullRawJson(true)}
                    className="text-xs"
                  >
                    Show all {rawJsonLineCount} lines
                  </Button>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Loading indicator when searching with existing results */}
      {isSearching && (
        <div className="flex items-center justify-center gap-2 py-2">
          <Loader2 className="size-4 animate-spin" />
          <span className="text-muted-foreground text-xs">
            Updating results...
          </span>
        </div>
      )}
    </div>
  );
}
