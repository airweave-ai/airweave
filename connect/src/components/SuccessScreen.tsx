import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { apiClient } from "../lib/api";
import { canConnect } from "../lib/connection-utils";
import { notifyConnectionCreated } from "../lib/messaging";
import { useTheme } from "../lib/theme";
import type { ConnectSessionContext, NavigateView, Source } from "../lib/types";
import { Button } from "./Button";
import { ConnectionItem } from "./ConnectionItem";
import { ConnectionsErrorView } from "./ConnectionsErrorView";
import { EmptyState } from "./EmptyState";
import { LoadingScreen } from "./LoadingScreen";
import { PageLayout } from "./PageLayout";
import { SourceConfigView } from "./SourceConfigView";
import { SourcesList } from "./SourcesList";

interface SuccessScreenProps {
  session: ConnectSessionContext;
  initialView?: NavigateView | null;
  onViewChange?: (view: NavigateView) => void;
}

export function SuccessScreen({
  session,
  initialView,
  onViewChange,
}: SuccessScreenProps) {
  const { labels } = useTheme();
  const queryClient = useQueryClient();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);

  const defaultView: NavigateView =
    session.mode === "connect" ? "sources" : "connections";

  const [internalView, setInternalView] = useState<NavigateView | null>(null);

  const view: NavigateView = initialView ?? internalView ?? defaultView;

  const setView = (newView: NavigateView) => {
    setInternalView(newView);
    onViewChange?.(newView);
  };

  const allowConnect = canConnect(session.mode);

  const {
    data: connections,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["source-connections"],
    queryFn: () => apiClient.getSourceConnections(),
    enabled: session.mode !== "connect",
  });

  const deleteMutation = useMutation({
    mutationFn: (connectionId: string) =>
      apiClient.deleteSourceConnection(connectionId),
    onMutate: (connectionId) => {
      setDeletingId(connectionId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["source-connections"] });
    },
    onSettled: () => {
      setDeletingId(null);
    },
  });

  const handleSelectSource = (source: Source) => {
    setSelectedSource(source);
    setView("configure");
  };

  // Configure view - show source configuration form
  if (view === "configure" && selectedSource) {
    return (
      <SourceConfigView
        source={selectedSource}
        onBack={() => {
          setSelectedSource(null);
          setView("sources");
        }}
        onSuccess={(connectionId) => {
          notifyConnectionCreated(connectionId);
          setSelectedSource(null);
          setView("connections");
          queryClient.invalidateQueries({ queryKey: ["source-connections"] });
        }}
      />
    );
  }

  if (view === "sources") {
    return (
      <SourcesList
        labels={labels}
        onBack={
          session.mode === "connect" ? null : () => setView("connections")
        }
        onSelectSource={handleSelectSource}
      />
    );
  }

  if (isLoading) return <LoadingScreen />;

  if (error) {
    return <ConnectionsErrorView error={error} labels={labels} />;
  }

  const connectButton =
    allowConnect && connections && connections.length > 0 ? (
      <Button onClick={() => setView("sources")} className="px-3 gap-1.5">
        <Plus className="w-4 h-4" />
        {labels.buttonConnect}
      </Button>
    ) : undefined;

  return (
    <PageLayout title={labels.sourcesHeading} headerRight={connectButton}>
      {connections && connections.length > 0 ? (
        <div className="flex flex-col gap-3 pb-4">
          {connections.map((connection) => (
            <ConnectionItem
              key={connection.id}
              connection={connection}
              onDelete={() => deleteMutation.mutate(connection.id)}
              isDeleting={deletingId === connection.id}
              labels={labels}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          labels={labels}
          showConnect={allowConnect}
          onConnect={() => setView("sources")}
        />
      )}
    </PageLayout>
  );
}
