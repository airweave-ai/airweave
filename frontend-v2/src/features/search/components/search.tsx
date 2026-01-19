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
  const [searchResponse, setSearchResponse] =
    useState<SearchResponseType | null>(null);
  const [searchResponseType, setSearchResponseType] = useState<
    "raw" | "completion"
  >("raw");
  const [showResponsePanel, setShowResponsePanel] = useState<boolean>(false);
  const [isSearching, setIsSearching] = useState(false);
  const [liveResults, setLiveResults] = useState<unknown[]>([]);
  const [events, setEvents] = useState<SearchEvent[]>([]);

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
      if (!showResponsePanel) setShowResponsePanel(true);
      setIsSearching(true);
      setSearchResponse(null);
      setSearchResponseType(responseType);
      setLiveResults([]);
      setEvents([]);
    },
    [showResponsePanel]
  );

  const handleSearchEnd = useCallback(() => {
    setIsSearching(false);
  }, []);

  const handleStreamEvent = useCallback((event: SearchEvent) => {
    setEvents((prev) => [...prev, event]);
    if (event.type === "results") {
      setLiveResults(event.results);
    }
  }, []);

  const handleCancel = useCallback(() => {
    setEvents((prev) => [...prev, { type: "cancelled" } as SearchEvent]);
  }, []);

  return (
    <div className={cn("w-full", className)}>
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
