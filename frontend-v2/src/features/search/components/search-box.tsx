/**
 * SearchBox - Main search input with toggles and options
 */

import { X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";
import { useKeyboardShortcut } from "@/hooks/use-keyboard-shortcut";
import { API_BASE_URL, getAuthHeaders } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { cn } from "@/lib/utils";

import type {
  SearchEvent,
  SearchMethod,
  SearchResponse,
  SearchToggles,
} from "../types";
import { ApiIntegrationModal } from "./api-integration-modal";
import { CodeButton } from "./code-button";
import { SearchInput } from "./search-input";
import { SearchMethodSelector } from "./search-method-selector";
import { SearchSubmitButton } from "./search-submit-button";
import { SearchTogglesPanel } from "./search-toggles-panel";
import { useSearchStream } from "../hooks/use-search-stream";
import { useTooltipManager } from "../hooks/use-tooltip-manager";

interface UsageCheckResponse {
  allowed: boolean;
  reason?: "usage_limit_exceeded" | "payment_required" | string;
}

interface SearchBoxProps {
  collectionId: string;
  onSearch: (
    response: SearchResponse,
    responseType: "raw" | "completion",
    responseTime: number
  ) => void;
  onSearchStart?: (responseType: "raw" | "completion") => void;
  onSearchEnd?: () => void;
  onStreamEvent?: (event: SearchEvent) => void;
  onCancel?: () => void;
  className?: string;
}

const DEFAULT_TOGGLES: SearchToggles = {
  queryExpansion: true,
  filter: false,
  queryInterpretation: false,
  recencyBias: false,
  reRanking: true,
  answer: true,
};

export function SearchBox({
  collectionId,
  onSearch,
  onSearchStart,
  onSearchEnd,
  onStreamEvent,
  onCancel,
  className,
}: SearchBoxProps) {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const { executeSearch, cancelSearch } = useSearchStream();
  const tooltipManager = useTooltipManager();

  // Core search state
  const [query, setQuery] = useState("");
  const [searchMethod, setSearchMethod] = useState<SearchMethod>("hybrid");
  const [isSearching, setIsSearching] = useState(false);

  // Filter state
  const [filterJson, setFilterJson] = useState("");
  const [isFilterValid, setIsFilterValid] = useState(true);

  // Recency bias state
  const [recencyBiasValue, setRecencyBiasValue] = useState(0.0);

  // Toggle buttons state
  const [toggles, setToggles] = useState<SearchToggles>(DEFAULT_TOGGLES);

  // Code modal state
  const [showCodeModal, setShowCodeModal] = useState(false);
  const [apiKey, setApiKey] = useState<string>("YOUR_API_KEY");

  // Usage limits state
  const [queriesAllowed, setQueriesAllowed] = useState(true);
  const [queriesCheckDetails, setQueriesCheckDetails] =
    useState<UsageCheckResponse | null>(null);
  const [isCheckingUsage, setIsCheckingUsage] = useState(true);

  // Transient error handling
  const [transientIssue, setTransientIssue] = useState<{
    message: string;
  } | null>(null);

  const hasQuery = query.trim().length > 0;
  const canRetrySearch = Boolean(transientIssue) && !isSearching;
  const isSearchDisabled = !queriesAllowed || isCheckingUsage;

  // Check if queries are allowed based on usage limits
  const checkQueriesAllowed = useCallback(async () => {
    if (!organization) return;

    try {
      setIsCheckingUsage(true);
      const token = await getAccessTokenSilently();
      const response = await fetch(
        `${API_BASE_URL}/usage/check-action?action=queries`,
        {
          headers: getAuthHeaders(token, organization.id),
        }
      );
      if (response.ok) {
        const data: UsageCheckResponse = await response.json();
        setQueriesAllowed(data.allowed);
        setQueriesCheckDetails(data);
      } else {
        setQueriesAllowed(true);
        setQueriesCheckDetails(null);
      }
    } catch {
      setQueriesAllowed(true);
      setQueriesCheckDetails(null);
    } finally {
      setIsCheckingUsage(false);
    }
  }, [organization, getAccessTokenSilently]);

  // Initial usage check on mount
  useEffect(() => {
    checkQueriesAllowed();
  }, [checkQueriesAllowed]);

  // Fetch API key on mount for code modal
  useEffect(() => {
    const fetchApiKey = async () => {
      if (!organization) return;
      try {
        const token = await getAccessTokenSilently();
        const response = await fetch(`${API_BASE_URL}/api-keys`, {
          headers: getAuthHeaders(token, organization.id),
        });
        if (response.ok) {
          const data = await response.json();
          if (Array.isArray(data) && data.length > 0 && data[0].decrypted_key) {
            setApiKey(data[0].decrypted_key);
          }
        }
      } catch (err) {
        console.error("Error fetching API key:", err);
      }
    };
    fetchApiKey();
  }, [organization, getAccessTokenSilently]);

  // Handle escape key for modal
  useKeyboardShortcut({
    key: "Escape",
    onKeyDown: () => setShowCodeModal(false),
    enabled: showCodeModal,
  });

  // Manage body overflow when modal is open
  useEffect(() => {
    if (showCodeModal) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [showCodeModal]);

  // Cancel current search
  const handleCancelSearch = useCallback(() => {
    cancelSearch();
    onStreamEvent?.({ type: "cancelled" } as SearchEvent);
    onCancel?.();
    checkQueriesAllowed();
  }, [cancelSearch, onStreamEvent, onCancel, checkQueriesAllowed]);

  // Main search handler
  const handleSendQuery = useCallback(async () => {
    if (
      !hasQuery ||
      !collectionId ||
      isSearching ||
      !organization ||
      !queriesAllowed ||
      isCheckingUsage
    )
      return;

    setTransientIssue(null);
    const currentResponseType = toggles.answer ? "completion" : "raw";

    setIsSearching(true);
    onSearchStart?.(currentResponseType);

    try {
      const token = await getAccessTokenSilently();

      // Parse filter if enabled and valid
      let parsedFilter = null;
      if (toggles.filter && filterJson && isFilterValid) {
        try {
          parsedFilter = JSON.parse(filterJson);
        } catch {
          parsedFilter = null;
        }
      }

      const requestBody: Record<string, unknown> = {
        query: query,
        retrieval_strategy: searchMethod,
        expand_query: toggles.queryExpansion,
        interpret_filters: toggles.queryInterpretation,
        temporal_relevance: toggles.recencyBias ? recencyBiasValue : 0,
        rerank: toggles.reRanking,
        generate_answer: toggles.answer,
      };

      if (parsedFilter) {
        requestBody.filter = parsedFilter;
      }

      await executeSearch({
        collectionId,
        query,
        requestBody,
        token,
        orgId: organization.id,
        onStreamEvent,
        onSuccess: (response, responseTime) => {
          onSearch(response, currentResponseType, responseTime);
        },
        onError: (error, responseTime, isTransient) => {
          if (isTransient) {
            setTransientIssue({ message: error.message });
            onSearch(
              {
                results: [],
                error: "Something went wrong, please try again.",
                errorIsTransient: true,
              },
              currentResponseType,
              responseTime
            );
          } else {
            onSearch(
              { results: [], error: error.message, errorIsTransient: false },
              currentResponseType,
              responseTime
            );
          }
        },
      });
    } catch {
      // Error handled in onError callback
    } finally {
      setIsSearching(false);
      onSearchEnd?.();
      checkQueriesAllowed();
    }
  }, [
    hasQuery,
    collectionId,
    query,
    searchMethod,
    toggles,
    filterJson,
    isFilterValid,
    recencyBiasValue,
    isSearching,
    organization,
    queriesAllowed,
    isCheckingUsage,
    getAccessTokenSilently,
    executeSearch,
    onSearch,
    onSearchStart,
    onSearchEnd,
    onStreamEvent,
    checkQueriesAllowed,
  ]);

  // Handle toggle button clicks
  const handleToggle = useCallback(
    (name: keyof SearchToggles) => {
      if (name === "filter") {
        setToggles((prev) => {
          const newFilterState = !prev.filter;
          if (newFilterState) {
            tooltipManager.forceOpen("filter");
          }
          return { ...prev, filter: newFilterState };
        });
      } else if (name === "recencyBias") {
        setToggles((prev) => {
          const newState = !prev.recencyBias;
          if (newState) {
            tooltipManager.forceOpen("recencyBias");
          }
          return { ...prev, recencyBias: newState };
        });
      } else {
        setToggles((prev) => ({ ...prev, [name]: !prev[name] }));
      }
    },
    [tooltipManager]
  );

  // Handle recency bias slider changes
  const handleRecencyBiasChange = useCallback((value: number) => {
    setRecencyBiasValue(value);
    setToggles((prev) => ({ ...prev, recencyBias: value > 0 }));
  }, []);

  // Handle filter editor changes
  const handleFilterChange = useCallback((value: string, isValid: boolean) => {
    setFilterJson(value);
    setIsFilterValid(isValid);
  }, []);

  return (
    <>
      <div className={cn("w-full", className)}>
        <div className="bg-card overflow-hidden rounded-lg border">
          <div className="relative px-2 pt-2 pb-1">
            <CodeButton onClick={() => setShowCodeModal(true)} />
            <SearchInput
              value={query}
              onChange={setQuery}
              onSubmit={handleSendQuery}
              isDisabled={isSearchDisabled}
              isSearching={isSearching}
              usageLimit={
                isSearchDisabled
                  ? {
                      isChecking: isCheckingUsage,
                      isAllowed: queriesAllowed,
                      reason: queriesCheckDetails?.reason,
                    }
                  : undefined
              }
            />
          </div>

          <div className="flex items-center justify-between px-2 pb-2">
            <TooltipProvider delayDuration={0}>
              <div className="flex items-center gap-1.5">
                <SearchMethodSelector
                  value={searchMethod}
                  onChange={setSearchMethod}
                  openTooltip={tooltipManager.openTooltip}
                  onMouseEnter={tooltipManager.handleMouseEnter}
                  onMouseLeave={tooltipManager.handleMouseLeave}
                  onContentMouseEnter={tooltipManager.handleContentMouseEnter}
                  onContentMouseLeave={tooltipManager.handleContentMouseLeave}
                />
                <SearchTogglesPanel
                  toggles={toggles}
                  onToggle={handleToggle}
                  filterJson={filterJson}
                  onFilterChange={handleFilterChange}
                  recencyBiasValue={recencyBiasValue}
                  onRecencyBiasChange={handleRecencyBiasChange}
                  openTooltip={tooltipManager.openTooltip}
                  onMouseEnter={tooltipManager.handleMouseEnter}
                  onMouseLeave={tooltipManager.handleMouseLeave}
                  onContentMouseEnter={tooltipManager.handleContentMouseEnter}
                  onContentMouseLeave={tooltipManager.handleContentMouseLeave}
                />
              </div>

              <SearchSubmitButton
                isSearching={isSearching}
                hasQuery={hasQuery}
                queriesAllowed={queriesAllowed}
                isCheckingUsage={isCheckingUsage}
                canRetry={canRetrySearch}
                retryMessage={transientIssue?.message}
                onSubmit={handleSendQuery}
                onCancel={handleCancelSearch}
                onRetry={() => {
                  setTransientIssue(null);
                  handleSendQuery();
                }}
              />
            </TooltipProvider>
          </div>
        </div>
      </div>

      {/* Code Block Modal */}
      {showCodeModal && collectionId && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowCodeModal(false)}
          />
          <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center p-8">
            <div
              className="pointer-events-auto relative w-full max-w-4xl"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => setShowCodeModal(false)}
                className="bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground absolute top-2 right-2 z-10 flex size-8 items-center justify-center rounded-md transition-colors"
                title="Close (Esc)"
              >
                <X className="size-4" />
              </button>
              <ApiIntegrationModal
                collectionReadableId={collectionId}
                query={query || "Ask a question about your data"}
                searchConfig={{
                  search_method: searchMethod,
                  expansion_strategy: toggles.queryExpansion
                    ? "auto"
                    : "no_expansion",
                  enable_query_interpretation: toggles.queryInterpretation,
                  recency_bias: toggles.recencyBias ? recencyBiasValue : 0.0,
                  enable_reranking: toggles.reRanking,
                  response_type: toggles.answer ? "completion" : "raw",
                }}
                filter={toggles.filter ? filterJson : null}
                apiKey={apiKey}
              />
            </div>
          </div>
        </>
      )}
    </>
  );
}
