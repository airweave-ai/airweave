import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
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
  const [recentConnectionId, setRecentConnectionId] = useState<string | null>(null);

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
    onMutate: async (connectionId) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ["source-connections"] });

      // Snapshot the previous value
      const previousConnections = queryClient.getQueryData<
        SourceConnectionListItem[]
      >(["source-connections"]);

      // Optimistically remove the connection
      queryClient.setQueryData<SourceConnectionListItem[]>(
        ["source-connections"],
        (old) => old?.filter((c) => c.id !== connectionId) ?? [],
      );

      // Return context with the snapshot
      return { previousConnections };
    },
    onError: (_err, _connectionId, context) => {
      // Rollback on error
      if (context?.previousConnections) {
        queryClient.setQueryData(
          ["source-connections"],
          context.previousConnections,
        );
      }
    },
    onSettled: () => {
      // Always refetch to ensure sync
      queryClient.invalidateQueries({ queryKey: ["source-connections"] });
    },
  });

  // Reconnect flow for pending_auth connections
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
        onConnectionCreated(result.source_connection_id);
        queryClient.invalidateQueries({ queryKey: ["source-connections"] });
      }
    },
    [onConnectionCreated, queryClient]
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
          // Popup blocked - open in same window as fallback
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

  // Configure view - show source configuration form
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
          if (options.enableFolderSelection) {
            setRecentConnectionId(connectionId);
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

  // Folder selection view - show after OAuth when enabled
  if (view === "folder-selection" && selectedSource && recentConnectionId) {
    return (
      <FolderSelectionView
        source={selectedSource}
        connectionId={recentConnectionId}
        onBack={() => {
          // Cancel folder selection - go back to sources
          setRecentConnectionId(null);
          setSelectedSource(null);
          setView("sources");
        }}
        onComplete={() => {
          setRecentConnectionId(null);
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

  const connectButton =
    allowConnect && connections && connections.length > 0 ? (
      <Button onClick={() => setView("sources")} className="w-full justify-center">
        {labels.buttonConnect}
      </Button>
    ) : undefined;

  return (
    <PageLayout title={labels.sourcesHeading} footerContent={connectButton}>
      {connections && connections.length > 0 ? (
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
