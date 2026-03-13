import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSyncProgress } from "../hooks/useSyncProgress";
import { apiClient } from "../lib/api";
import { canConnect } from "../lib/connection-utils";
import { listenForOAuthComplete, openOAuthPopup } from "../lib/oauth";
import { useTheme } from "../lib/theme";
import type {
  ConnectSessionContext,
  NavigateView,
  OAuthCallbackResult,
  Source,
  SourceConnectionListItem,
} from "../lib/types";
import { Button } from "./Button";
import { ConnectionItem } from "./ConnectionItem";
import { ConnectionsErrorView } from "./ConnectionsErrorView";
import { EmptyState } from "./EmptyState";
import { FolderSelectionView } from "./FolderSelectionView";
import { LoadingScreen } from "./LoadingScreen";
import { PageLayout } from "./PageLayout";
import { SourceConfigView } from "./SourceConfigView";
import { SourcesList } from "./SourcesList";

interface SuccessScreenProps {
  session: ConnectSessionContext;
  initialView?: NavigateView | null;
  onViewChange?: (view: NavigateView) => void;
  onConnectionCreated: (connectionId: string) => void;
}

export function SuccessScreen({
  session,
  initialView,
  onViewChange,
  onConnectionCreated,
}: SuccessScreenProps) {
  const { labels, options } = useTheme();
  const queryClient = useQueryClient();
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [recentConnectionId, setRecentConnectionId] = useState<string | null>(
    null,
  );

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
    // Poll every 5s while any connection is syncing to catch external state
    // changes (cancellation, completion) that SSE might miss
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.some((c) => c.status === "syncing")) return 5000;
      return false;
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (connectionId: string) =>
      apiClient.deleteSourceConnection(connectionId),
    onMutate: async (connectionId) => {
      await queryClient.cancelQueries({ queryKey: ["source-connections"] });

      const previousConnections = queryClient.getQueryData<
        SourceConnectionListItem[]
      >(["source-connections"]);

      queryClient.setQueryData<SourceConnectionListItem[]>(
        ["source-connections"],
        (old) => old?.filter((c) => c.id !== connectionId) ?? [],
      );

      return { previousConnections };
    },
    onError: (_err, _connectionId, context) => {
      if (context?.previousConnections) {
        queryClient.setQueryData(
          ["source-connections"],
          context.previousConnections,
        );
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["source-connections"] });
    },
  });

  const {
    subscribe,
    getProgress,
    isReconnecting: isSseReconnecting,
  } = useSyncProgress({
    onComplete: () => {
      queryClient.invalidateQueries({ queryKey: ["source-connections"] });
    },
  });

  useEffect(() => {
    if (!connections) return;

    connections
      .filter((c) => c.status === "syncing")
      .forEach((c) => subscribe(c.id));
  }, [connections, subscribe]);

  // Immediately subscribe to SSE for recently created connection
  // This eliminates the gap between folder selection and connections query returning
  useEffect(() => {
    if (recentConnectionId && view === "connections") {
      subscribe(recentConnectionId);
    }
  }, [recentConnectionId, view, subscribe]);

  const reconnectPopupRef = useRef<Window | null>(null);
  const [isReconnecting, setIsReconnecting] = useState(false);

  const handleOAuthResult = useCallback(
    (result: OAuthCallbackResult) => {
      if (reconnectPopupRef.current && !reconnectPopupRef.current.closed) {
        reconnectPopupRef.current.close();
      }
      reconnectPopupRef.current = null;
      setIsReconnecting(false);

      if (result.status === "success" && result.source_connection_id) {
        setRecentConnectionId(result.source_connection_id);
        onConnectionCreated(result.source_connection_id);
        queryClient.invalidateQueries({ queryKey: ["source-connections"] });
      }
    },
    [onConnectionCreated, queryClient],
  );

  useEffect(() => {
    if (!isReconnecting) return;

    const cleanup = listenForOAuthComplete(handleOAuthResult);
    return () => cleanup();
  }, [isReconnecting, handleOAuthResult]);

  const handleReconnect = async (connectionId: string) => {
    try {
      setIsReconnecting(true);
      const connection = await apiClient.getSourceConnection(connectionId);

      if (connection.auth?.auth_url) {
        const popup = openOAuthPopup({ url: connection.auth.auth_url });
        if (popup) {
          reconnectPopupRef.current = popup;
        } else {
          window.location.assign(connection.auth.auth_url);
        }
      } else {
        setIsReconnecting(false);
      }
    } catch {
      setIsReconnecting(false);
    }
  };

  const handleSelectSource = (source: Source) => {
    setSelectedSource(source);
    setView("configure");
  };

  if (view === "configure" && selectedSource) {
    return (
      <SourceConfigView
        source={selectedSource}
        collectionId={session.collection_id}
        onBack={() => {
          setSelectedSource(null);
          setView("sources");
        }}
        onSuccess={(connectionId) => {
          onConnectionCreated(connectionId);
          setRecentConnectionId(connectionId);
          if (options.enableFolderSelection) {
            setView("folder-selection");
          } else {
            setSelectedSource(null);
            setView("connections");
            queryClient.invalidateQueries({ queryKey: ["source-connections"] });
          }
        }}
      />
    );
  }

  if (view === "folder-selection" && selectedSource && recentConnectionId) {
    return (
      <FolderSelectionView
        source={selectedSource}
        connectionId={recentConnectionId}
        onBack={() => {
          setRecentConnectionId(null);
          setSelectedSource(null);
          setView("sources");
        }}
        onComplete={() => {
          // Keep recentConnectionId to trigger immediate SSE subscription
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
          session.mode === "connect"
            ? null
            : () => {
              setView("connections");
              queryClient.invalidateQueries({
                queryKey: ["source-connections"],
              });
            }
        }
        onSelectSource={handleSelectSource}
      />
    );
  }

  if (isLoading) return <LoadingScreen />;

  if (error) {
    return <ConnectionsErrorView error={error} labels={labels} />;
  }

  const hasConnections = connections && connections.length > 0;

  const connectButton = allowConnect ? (
    <Button
      onClick={() => setView("sources")}
      className="w-full justify-center"
    >
      {labels.buttonConnect}
      {!hasConnections && <ArrowRight size={16} />}
    </Button>
  ) : undefined;

  return (
    <PageLayout
      title={hasConnections ? labels.sourcesHeading : undefined}
      footerContent={connectButton}
      hideHeader={!hasConnections}
    >
      {hasConnections ? (
        <div className="flex flex-col gap-3 pb-4">
          {connections.map((connection) => (
            <ConnectionItem
              key={connection.id}
              connection={connection}
              onReconnect={
                connection.status === "pending_auth"
                  ? () => handleReconnect(connection.id)
                  : undefined
              }
              onDelete={() => deleteMutation.mutate(connection.id)}
              labels={labels}
              syncProgress={getProgress(connection.id)}
              isSseReconnecting={isSseReconnecting(connection.id)}
            />
          ))}
        </div>
      ) : (
        <EmptyState labels={labels} showConnect={allowConnect} />
      )}
    </PageLayout>
  );
}
