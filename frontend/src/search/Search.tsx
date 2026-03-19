import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import { SearchBox, type SearchTier } from "@/search/SearchBox";
import { SearchResponse } from "@/search/SearchResponse";
import { DESIGN_SYSTEM } from "@/lib/design-system";
import { useOrganizationStore } from "@/lib/stores/organizations";
import { FeatureFlags } from "@/lib/constants/feature-flags";

interface SearchProps {
    collectionReadableId: string;
    disabled?: boolean;
}

/**
 * Search Component
 *
 * Orchestrates SearchBox (query input + tier selection) and SearchResponse (results display).
 */
export const Search = ({ collectionReadableId, disabled = false }: SearchProps) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    const agenticEnabled = useOrganizationStore((state) => state.hasFeature(FeatureFlags.AGENTIC_SEARCH));

    // Search tier
    const [tier, setTier] = useState<SearchTier>("classic");

    // Response state
    const [searchResponse, setSearchResponse] = useState<any>(null);
    const [responseTime, setResponseTime] = useState<number | null>(null);

    // Streaming lifecycle
    const [showResponsePanel, setShowResponsePanel] = useState<boolean>(false);
    const [requestId, setRequestId] = useState<string | null>(null);
    const [events, setEvents] = useState<any[]>([]);
    const [isSearching, setIsSearching] = useState(false);

    const handleSearchResult = useCallback((response: any, _responseType: 'raw' | 'completion', responseTimeMs: number) => {
        setSearchResponse(response);
        setResponseTime(responseTimeMs);
    }, []);

    const handleSearchStart = useCallback((_responseType: 'raw' | 'completion') => {
        if (!showResponsePanel) setShowResponsePanel(true);
        setIsSearching(true);
        setSearchResponse(null);
        setResponseTime(null);
        setEvents([]);
        setRequestId(null);
    }, [showResponsePanel]);

    const handleSearchEnd = useCallback(() => {
        setIsSearching(false);
    }, []);


    return (
        <div
            className={cn(
                "w-full max-w-[1000px]",
                DESIGN_SYSTEM.spacing.margins.section,
                isDark ? "text-foreground" : ""
            )}
        >
            <div>
                <SearchBox
                    collectionId={collectionReadableId}
                    disabled={disabled}
                    agenticEnabled={agenticEnabled}
                    tier={tier}
                    onTierChange={setTier}
                    onSearch={handleSearchResult}
                    onSearchStart={handleSearchStart}
                    onSearchEnd={handleSearchEnd}
                    onCancel={() => {
                        setSearchResponse((prev: any) => prev || { results: [] });
                        setIsSearching(false);
                        setEvents(prev => [...prev, { type: 'cancelled' as const }]);
                    }}
                    onStreamEvent={(event: any) => {
                        setEvents(prev => [...prev, event]);
                        if (event?.type === 'started' && event.request_id) {
                            setRequestId(event.request_id as string);
                        }
                    }}
                    onStreamUpdate={(partial: any) => {
                        if (partial && Object.prototype.hasOwnProperty.call(partial, 'requestId')) {
                            setRequestId(partial.requestId ?? null);
                        }
                    }}
                />
            </div>

            {showResponsePanel && (
                <div>
                    <SearchResponse
                        searchResponse={searchResponse}
                        isSearching={isSearching}
                        events={events as any[]}
                        showTrace={tier !== "instant" && tier !== "classic"}
                    />
                </div>
            )}
        </div>
    );
};
