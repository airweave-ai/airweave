import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { apiClient } from "../lib/api";
import type { ConnectLabels, Source } from "../lib/types";
import { LoadingScreen } from "./LoadingScreen";
import { PoweredByAirweave } from "./PoweredByAirweave";
import { SourceItem } from "./SourceItem";

interface SourcesListProps {
  labels: Required<ConnectLabels>;
  onBack: (() => void) | null;
  onSelectSource: (source: Source) => void;
}

export function SourcesList({
  labels,
  onBack,
  onSelectSource,
}: SourcesListProps) {
  const {
    data: sources,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["sources"],
    queryFn: () => apiClient.getSources(),
  });

  return (
    <div
      className="h-screen flex flex-col"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
      {/* Fixed Header */}
      <header className="flex-shrink-0 p-6 pb-4">
        <div className="flex items-center gap-3">
          {onBack && (
            <button
              onClick={onBack}
              className="p-1 rounded cursor-pointer border-none bg-transparent flex items-center justify-center transition-colors duration-150 hover:bg-black/10 dark:hover:bg-white/10"
              style={{ color: "var(--connect-text-muted)" }}
            >
              <ArrowLeft size={20} />
            </button>
          )}
          <div>
            <h1
              className="font-medium text-lg"
              style={{ color: "var(--connect-text)" }}
            >
              {labels.sourcesListHeading}
            </h1>
          </div>
        </div>
      </header>

      {/* Scrollable Content */}
      <main className="flex-1 overflow-y-auto px-6 scrollable-content">
        {isLoading && (
          <div className="h-full flex items-center justify-center">
            <LoadingScreen inline />
          </div>
        )}

        {error && (
          <div
            className="h-full flex items-center justify-center"
            style={{ color: "var(--connect-error)" }}
          >
            {error instanceof Error ? error.message : "An error occurred"}
          </div>
        )}

        {sources && sources.length === 0 && (
          <div
            className="h-full flex items-center justify-center"
            style={{ color: "var(--connect-text-muted)" }}
          >
            {labels.sourcesListEmpty}
          </div>
        )}

        {sources && sources.length > 0 && (
          <div className="flex flex-col gap-2 pb-4">
            {sources.map((source) => (
              <SourceItem
                key={source.short_name}
                source={source}
                onClick={() => onSelectSource(source)}
              />
            ))}
          </div>
        )}
      </main>

      {/* Fixed Footer */}
      <footer className="flex-shrink-0">
        <PoweredByAirweave />
      </footer>
    </div>
  );
}
