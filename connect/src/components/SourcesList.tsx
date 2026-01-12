import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../lib/api";
import type { ConnectLabels, Source } from "../lib/types";
import { BackButton } from "./BackButton";
import { LoadingScreen } from "./LoadingScreen";
import { PageLayout } from "./PageLayout";
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

  const backButton = onBack ? <BackButton onClick={onBack} /> : undefined;

  return (
    <PageLayout title={labels.sourcesListHeading} headerLeft={backButton}>
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
    </PageLayout>
  );
}
