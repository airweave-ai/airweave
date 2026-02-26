import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import { SearchBox, type SearchMode } from "@/search/SearchBox";
import { SearchResponse } from "@/search/SearchResponse";
import { DESIGN_SYSTEM } from "@/lib/design-system";
import { useOrganizationStore } from "@/lib/stores/organizations";
import { FeatureFlags } from "@/lib/constants/feature-flags";

interface SearchProps {
    collectionReadableId: string;
    disabled?: boolean;  // Disable search when no sources are connected
}

/**
 * Search Component
 *
 * The main search component for a collection, providing:
 * - SearchBox for query input and configuration
 * - SearchResponseDisplay for showing results
 * - Clean separation of concerns for maintainability
 */
export const Search = ({ collectionReadableId, disabled = false }: SearchProps) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    // Check if the organization has the agentic search feature flag
    const agenticEnabled = useOrganizationStore((state) => state.hasFeature(FeatureFlags.AGENTIC_SEARCH));

    // Search mode (search vs agent) — defaults to agent only if feature is enabled
    const [searchMode, setSearchMode] = useState<SearchMode>(agenticEnabled ? "agent" : "search");

    // Search response state (final)
    const [searchResponse, setSearchResponse] = useState<any>(null);
    const [responseTime, setResponseTime] = useState<number | null>(null);
    const [searchResponseType, setSearchResponseType] = useState<'raw' | 'completion'>('raw');

    // Streaming lifecycle state (Milestone 1)
    const [showResponsePanel, setShowResponsePanel] = useState<boolean>(false);

    const [requestId, setRequestId] = useState<string | null>(null);
    const [events, setEvents] = useState<any[]>([]);

    // live results while searching
    const [liveResults, setLiveResults] = useState<any[]>([]);

    // search state
    const [isCancelling, setIsCancelling] = useState<boolean>(false);
    const [isSearching, setIsSearching] = useState(false);

    // Handle search results from SearchBox
    const handleSearchResult = useCallback((response: any, responseType: 'raw' | 'completion', responseTimeMs: number) => {
        setSearchResponse(response);
        setSearchResponseType(responseType);
        setResponseTime(responseTimeMs);
    }, []);

    const handleSearchStart = useCallback((responseType: 'raw' | 'completion') => {
        // Open panels on first search
        if (!showResponsePanel) setShowResponsePanel(true);

        // Reset per-search state
        setIsSearching(true);
        setIsCancelling(false);
        setSearchResponse(null);
        setResponseTime(null);
        setSearchResponseType(responseType);  // Set the response type for this search
        setEvents([]);
        setLiveResults([]);
        setRequestId(null);
    }, [showResponsePanel]);

    const handleSearchEnd = useCallback(() => {

        setIsSearching(false);
        setIsCancelling(false);

        // Don't hide the panel here - the panel visibility should be determined by
        // whether we have content to show, not by stale closure values
        // The issue was that this callback was capturing initial null/empty values
    }, []);

    return (
        <div
            className={cn(
                "w-full max-w-[1000px]",
                DESIGN_SYSTEM.spacing.margins.section,
                isDark ? "text-foreground" : ""
            )}
        >
            {/* Search Box Component */}
            <div>
                <SearchBox
                    collectionId={collectionReadableId}
                    disabled={disabled}
                    agenticEnabled={agenticEnabled}
                    searchMode={searchMode}
                    onSearchModeChange={setSearchMode}
                    onSearch={handleSearchResult}
                    onSearchStart={handleSearchStart}
                    onSearchEnd={handleSearchEnd}
                    onCancel={() => {
                        setIsCancelling(true);
                        // If we don't yet have a final response, expose a cancelled placeholder
                        setSearchResponse((prev) => {
                            const next = prev || { results: [], completion: null };
                            return next;
                        });
                        setSearchResponseType((prev) => {
                            return prev;
                        });
                        setIsSearching(false);
                    }}
                    onStreamEvent={(event: any) => {
                        setEvents(prev => [...prev, event]);
                        if (event?.type === 'cancelled') {
                            setIsCancelling(true);
                            setIsSearching(false);
                            setSearchResponse((prev) => prev || { results: [], completion: null });
                        }
                        if (event?.type === 'connected' && event.request_id) {
                            setRequestId(event.request_id as string);
                        }
                    }}
                    onStreamUpdate={(partial: any) => {
                        if (partial && Object.prototype.hasOwnProperty.call(partial, 'requestId')) {
                            setRequestId(partial.requestId ?? null);
                        }
                        if (Array.isArray(partial?.results)) {
                            setLiveResults(partial.results);
                        }
                    }}
                />
            </div>

            {/* Search Response Display - visibility controlled by panel state (Milestone 1) */}
            {showResponsePanel && (
                <div>
                    <SearchResponse
                        searchResponse={(() => {
                            // While searching, show live results but no completion (not streamed)
                            const response = isSearching
                                ? { results: liveResults }
                                : searchResponse;
                            return response;
                        })()}
                        isSearching={isSearching}
                        responseType={searchResponseType}
                        events={events as any[]}
                    />
                </div>
            )}
        </div>
    );
};
