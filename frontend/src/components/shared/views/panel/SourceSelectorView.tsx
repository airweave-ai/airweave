/**
 * SourceSelectorView.tsx
 *
 * This component displays a grid of available data sources that users can select
 * to connect to their collection.
 */

import React, { useState, useEffect } from "react";
import { DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { redirectWithError } from "@/lib/error-utils";
import { SourceButton } from "@/components/dashboard/SourceButton";

/**
 * Interface for source data from API
 */
interface Source {
    /** Display name */
    name: string;
    /** Optional description */
    description?: string | null;
    /** Short name identifier (e.g., "github", "notion") */
    short_name: string;
    /** Optional categorization labels */
    labels?: string[];
}

/**
 * Props for the SourceSelectorView component
 */
export interface SourceSelectorViewProps {
    onNext?: (data?: any) => void;
    onBack?: () => void;
    onCancel?: () => void;
    onComplete?: (data?: any) => void;
    onError?: (error: Error | string, errorSource?: string) => void;
    viewData?: Record<string, any>;
}

/**
 * SourceSelectorView Component
 *
 * Grid display of available data sources with search functionality.
 * Allows selection of a source to connect to a collection.
 */
export const SourceSelectorView: React.FC<SourceSelectorViewProps> = ({
    onNext,
    onBack,
    onCancel,
    onComplete,
    onError,
    viewData = {},
}) => {
    /** List of available sources from API */
    const [sources, setSources] = useState<Source[]>([]);
    /** Loading state during API fetch */
    const [isLoading, setIsLoading] = useState(true);
    /** Error message if source fetch fails */
    const [error, setError] = useState<string | null>(null);
    /** Search query for filtering sources */
    const [searchQuery, setSearchQuery] = useState("");
    /** For navigation */
    const navigate = useNavigate();

    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const { collectionId, collectionName } = viewData;

    /**
     * Handle errors by redirecting to dashboard with error parameters
     */
    const handleError = (error: Error | string, errorType: string) => {
        console.error(`❌ [SourceSelectorView] ${errorType}:`, error);

        // Create the service name with collection info if available
        const service = collectionId && collectionName ?
            `Collection: ${collectionName}` : "Source Selection";

        if (onError) {
            onError(error, service);
        } else {
            // Use the common error utility to redirect with dialogId
            const errorDetails = {
                serviceName: service,
                sourceShortName: undefined, // No specific source selected yet
                errorMessage: error instanceof Error ? error.message : String(error),
                errorDetails: error instanceof Error ? error.stack : undefined,
                dialogId: viewData?.dialogId, // Include dialogId from viewData
                timestamp: Date.now()
            };

            redirectWithError(navigate, errorDetails, service);
        }
    };

    /**
     * Fetch available sources from API
     */
    useEffect(() => {
        const fetchSources = async () => {
            setIsLoading(true);
            setError(null);

            try {
                const response = await apiClient.get("/sources/");
                if (response.ok) {
                    const data = await response.json();
                    setSources(data);
                } else {
                    const errorText = await response.text();
                    throw new Error(`Failed to load sources: ${errorText}`);
                }
            } catch (err) {
                console.error("Error fetching sources:", err);
                handleError(err instanceof Error ? err : new Error(String(err)), "Failed to fetch sources");
            } finally {
                setIsLoading(false);
            }
        };

        fetchSources();
    }, []);

    /**
     * Handle source selection - simplified to just pass source data to next view
     */
    const handleSourceSelect = (source: Source) => {
        console.log(`Selected source: ${source.name} (${source.short_name})`);

        // Include collection data from viewData in the data passed to next view
        onNext?.({
            sourceId: source.short_name,
            sourceName: source.name,
            sourceShortName: source.short_name,
            // Preserve collection data
            collectionId: viewData.collectionId,
            collectionName: viewData.collectionName
        });
    };

    /**
     * Filter sources based on search query
     * Matches on name or short_name (case insensitive)
     */
    const filteredSources = searchQuery
        ? sources.filter(source =>
            source.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            source.short_name.toLowerCase().includes(searchQuery.toLowerCase())
        )
        : sources;

    // Sort sources alphabetically by name
    const sortedFilteredSources = [...filteredSources].sort((a, b) =>
        a.name.localeCompare(b.name)
    );

    return (
        <div className="flex flex-col h-full">
            {/* Header section - fixed */}
            <div className="flex-shrink-0 p-8 pb-4">
                <DialogTitle className="text-2xl font-semibold text-left">
                    {collectionId
                        ? `Add source connection to "${collectionName || collectionId}"`
                        : "Select a source to connect"
                    }
                </DialogTitle>
                {collectionId && (
                    <DialogDescription className="text-sm text-muted-foreground mt-1">
                        <span className="font-mono">{collectionId}</span>
                    </DialogDescription>
                )}

                {/* Search */}
                <div className="relative mt-6 mb-2">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        className="pl-10"
                        placeholder="Search sources..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>

            {/* Sources Grid - Scrollable section */}
            <div className="flex-grow overflow-y-auto p-8 pt-2">
                {isLoading ? (
                    <div className="flex flex-col items-center justify-center py-12">
                        <Loader2 className="h-8 w-8 animate-spin text-primary mb-2" />
                        <p className="text-muted-foreground">Loading available sources...</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-2 gap-3">
                        {sortedFilteredSources.map((source) => (
                            <SourceButton
                                key={source.short_name}
                                id={source.short_name}
                                name={source.name}
                                shortName={source.short_name}
                                onClick={() => handleSourceSelect(source)}
                            />
                        ))}

                        {sortedFilteredSources.length === 0 && (
                            <div className="col-span-2 text-center py-8 text-muted-foreground">
                                <p>No sources found matching your search.</p>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Footer - Fixed section */}
            <div className="flex-shrink-0 border-t">
                <DialogFooter className="p-6">
                    <Button
                        type="button"
                        variant="outline"
                        onClick={onCancel}
                        className={cn(
                            "px-6",
                            isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-300 hover:bg-gray-100"
                        )}
                    >
                        Cancel
                    </Button>
                </DialogFooter>
            </div>
        </div>
    );
};

export default SourceSelectorView;
