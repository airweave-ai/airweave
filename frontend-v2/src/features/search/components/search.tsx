/**
 * Search Component
 *
 * The main search component for a collection, combining:
 * - SearchBox for query input and configuration
 * - SearchResponse for showing results
 *
 * Features:
 * - Streaming search with real-time event tracking
 * - Response time measurement
 * - Trace view for search pipeline operations
 */

import { useCallback, useState } from "react";

import { cn } from "@/lib/utils";

import type {
  SearchEvent,
  SearchResponse as SearchResponseType,
} from "../types";
import { SearchBox } from "./search-box";
import { SearchResponse } from "./search-response";

interface SearchProps {
  collectionReadableId: string;
  className?: string;
  disabled?: boolean;
  disabledReason?: string;
}

export function Search({
  collectionReadableId,
  className,
  disabled,
  disabledReason,
}: SearchProps) {
  // Search response state
  const [searchResponse, setSearchResponse] =
    useState<SearchResponseType | null>(null);
  const [searchResponseType, setSearchResponseType] = useState<
    "raw" | "completion"
  >("raw");

  // Streaming lifecycle state
  const [showResponsePanel, setShowResponsePanel] = useState<boolean>(false);
  const [isSearching, setIsSearching] = useState(false);

  // Live results while searching
  const [liveResults, setLiveResults] = useState<unknown[]>([]);

  // Events for trace view
  const [events, setEvents] = useState<SearchEvent[]>([]);

  // Handle search results from SearchBox
  const handleSearchResult = useCallback(
    (
      response: SearchResponseType,
      responseType: "raw" | "completion",
      _responseTimeMs: number
    ) => {
      setSearchResponse(response);
      setSearchResponseType(responseType);
    },
    []
  );

  const handleSearchStart = useCallback(
    (responseType: "raw" | "completion") => {
      // Open panels on first search
      if (!showResponsePanel) setShowResponsePanel(true);

      // Reset per-search state
      setIsSearching(true);
      setSearchResponse(null);
      setSearchResponseType(responseType);
      setLiveResults([]);
      setEvents([]); // Clear previous events
    },
    [showResponsePanel]
  );

  const handleSearchEnd = useCallback(() => {
    setIsSearching(false);
  }, []);

  // Handle streaming events for trace
  const handleStreamEvent = useCallback((event: SearchEvent) => {
    setEvents((prev) => [...prev, event]);

    // Also update live results if this is a results event
    if (event.type === "results") {
      setLiveResults(event.results);
    }
  }, []);

  // Handle cancellation
  const handleCancel = useCallback(() => {
    // Add cancelled event to trace
    setEvents((prev) => [...prev, { type: "cancelled" } as SearchEvent]);
  }, []);

  return (
    <div className={cn("w-full", className)}>
      {/* Search Box Component */}
      <div>
        <SearchBox
          collectionId={collectionReadableId}
          onSearch={handleSearchResult}
          onSearchStart={handleSearchStart}
          onSearchEnd={handleSearchEnd}
          onStreamEvent={handleStreamEvent}
          onCancel={handleCancel}
          disabled={disabled}
          disabledReason={disabledReason}
        />
      </div>

      {/* Search Response Display */}
      {showResponsePanel && (
        <div>
          <SearchResponse
            searchResponse={
              isSearching ? { results: liveResults } : searchResponse
            }
            isSearching={isSearching}
            responseType={searchResponseType}
            events={events}
          />
        </div>
      )}
    </div>
  );
}
