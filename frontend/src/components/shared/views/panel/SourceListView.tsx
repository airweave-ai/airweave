import React, { useState } from "react";
import { Input } from "@/components/ui/input";
import { Search, Loader2 } from "lucide-react";
import { SourceButton } from "@/components/dashboard/SourceButton";
import { useSourcesStore } from "@/lib/stores/sources";
import { useSidePanelStore } from "@/lib/stores/sidePanelStore";

interface SourceListViewProps {
    context: {
        collectionId?: string;
        collectionName?: string;
    };
}

export const SourceListView: React.FC<SourceListViewProps> = ({ context }) => {
    const { sources, isLoading } = useSourcesStore();
    const { setView } = useSidePanelStore.getState();
    const [searchQuery, setSearchQuery] = useState("");

    const handleSourceSelect = (source: any) => {
        setView('sourceConfig', {
            sourceId: source.short_name,
            sourceName: source.name,
            sourceShortName: source.short_name,
        });
    };

    const filteredSources = searchQuery
        ? sources.filter(source =>
            source.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            source.short_name.toLowerCase().includes(searchQuery.toLowerCase())
        )
        : sources;

    const sortedFilteredSources = [...filteredSources].sort((a, b) => a.name.localeCompare(b.name));

    return (
        <div className="p-6 flex flex-col h-full">
            <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                    className="pl-10"
                    placeholder="Search sources..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />
            </div>
            <div className="flex-grow overflow-y-auto -mr-6 pr-6">
                {isLoading ? (
                    <div className="flex items-center justify-center h-full">
                        <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    </div>
                ) : (
                    <div className="grid grid-cols-1 gap-3">
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
                            <div className="col-span-full text-center py-8 text-muted-foreground">
                                <p>No sources found.</p>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
