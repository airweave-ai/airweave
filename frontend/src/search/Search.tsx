import { useState, useCallback, useRef } from "react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import { SearchBox, type SearchTier } from "@/search/SearchBox";
import { SearchResponse } from "@/search/SearchResponse";
import { DESIGN_SYSTEM } from "@/lib/design-system";
import { injectMockEvents } from "@/search/mockEvents";
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
    const mockCleanupRef = useRef<(() => void) | null>(null);

    // ⚠️  DEMO MODE — set to true to use mock events instead of the real backend
    const DEMO_MODE = true;

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

        if (DEMO_MODE) {
            mockCleanupRef.current?.();
            mockCleanupRef.current = injectMockEvents(setEvents, 1);
        }
    }, [showResponsePanel, DEMO_MODE]);

    const handleSearchEnd = useCallback(() => {
        setIsSearching(false);
        mockCleanupRef.current?.();
        mockCleanupRef.current = null;
    }, []);

    // In demo mode, watch for the 'done' event to finalize the search lifecycle
    const prevEventsLenRef = useRef(0);
    if (DEMO_MODE && events.length > prevEventsLenRef.current) {
        const latest = events[events.length - 1] as any;
        if (latest?.type === 'done' && isSearching) {
            setTimeout(() => {
                setIsSearching(false);
                setSearchResponse({ results: [], responseTime: latest.duration_ms });
                setResponseTime(latest.duration_ms);
            }, 0);
        }
    }
    prevEventsLenRef.current = events.length;


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
                    demoMode={DEMO_MODE}
                    agenticEnabled
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
