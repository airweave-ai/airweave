/**
 * SourceConnectionStateView - Main connection detail view with sync controls
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  cancelSourceConnectionSync,
  deleteSourceConnection,
  fetchSourceConnection,
  runSourceConnectionSync,
  type SourceConnection,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";

import { DeleteSourceDialog } from "./delete-source-dialog";
import { EntityStateList } from "./entity-state-list";
import { FederatedSearchInfo } from "./federated-search-info";
import { SourceAuthenticationView } from "./source-authentication-view";
import { SyncErrorCard } from "./sync-error-card";
import { SyncStatusDashboard } from "./sync-status-dashboard";

interface SourceConnectionStateViewProps {
  sourceConnection: SourceConnection;
  onConnectionDeleted?: () => void;
  onConnectionUpdated?: () => void;
}

function formatTimeAgo(dateStr: string | undefined): string | null {
  if (!dateStr) return null;

  const hasTimezone =
    dateStr.endsWith("Z") ||
    dateStr.match(/[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:?\d{2}$/);
  const utcDateStr = hasTimezone ? dateStr : `${dateStr}Z`;
  const date = new Date(utcDateStr);
  const now = new Date();

  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHrs > 0) return `${diffHrs}h ago`;
  if (diffMins > 0) return `${diffMins}m ago`;
  return "Just now";
}

function getSyncStatusDisplay(
  isNotAuthorized: boolean,
  isFederatedSource: boolean,
  syncState: "IDLE" | "SYNCING" | "CANCELLING",
  jobStatus?: string
) {
  if (isNotAuthorized) {
    return { text: "Not Authenticated", color: "bg-cyan-500", icon: null };
  }
  if (isFederatedSource) {
    return { text: "Ready", color: "bg-green-500", icon: null };
  }
  if (syncState === "CANCELLING") {
    return {
      text: "Cancelling",
      color: "bg-orange-500 animate-pulse",
      icon: "loader" as const,
    };
  }
  if (jobStatus === "failed") {
    return { text: "Failed", color: "bg-red-500", icon: null };
  }
  if (jobStatus === "completed") {
    return { text: "Completed", color: "bg-green-500", icon: null };
  }
  if (jobStatus === "cancelled") {
    return { text: "Cancelled", color: "bg-gray-500", icon: null };
  }
  if (jobStatus === "running" || jobStatus === "in_progress") {
    return {
      text: "Syncing",
      color: "bg-blue-500 animate-pulse",
      icon: "loader" as const,
    };
  }
  if (jobStatus === "pending" || jobStatus === "created") {
    return {
      text: "Pending",
      color: "bg-yellow-500 animate-pulse",
      icon: "loader" as const,
    };
  }
  return { text: "Ready", color: "bg-gray-400", icon: null };
}

export function SourceConnectionStateView({
  sourceConnection: initialSourceConnection,
  onConnectionDeleted,
  onConnectionUpdated,
}: SourceConnectionStateViewProps) {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const queryClient = useQueryClient();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isRefreshingAuth, setIsRefreshingAuth] = useState(false);

  if (!organization) {
    throw new Error("Organization context is required");
  }
  const orgId = organization.id;

  // Fetch detailed source connection data
  const { data: detailedConnection } = useQuery({
    queryKey: queryKeys.sourceConnections.detail(
      orgId,
      initialSourceConnection.id
    ),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSourceConnection(token, orgId, initialSourceConnection.id);
    },
    initialData: initialSourceConnection,
    refetchOnMount: true,
    staleTime: 0,
  });

  const sourceConnection = detailedConnection || initialSourceConnection;
  const isFederatedSource = sourceConnection.federated_search === true;
  const isNotAuthorized =
    sourceConnection.status === "pending_auth" ||
    !sourceConnection.auth?.authenticated;

  const currentSyncJob = sourceConnection.last_sync_job;
  const jobStatus = currentSyncJob?.status;

  const syncState = useMemo(() => {
    if (jobStatus === "cancelling") return "CANCELLING" as const;
    if (
      ["running", "in_progress", "pending", "created"].includes(jobStatus || "")
    ) {
      return "SYNCING" as const;
    }
    return "IDLE" as const;
  }, [jobStatus]);

  const isRunning = jobStatus === "running" || jobStatus === "in_progress";
  const isPending = jobStatus === "pending" || jobStatus === "created";
  const isSyncing = syncState !== "IDLE";

  // Run sync mutation
  const runSyncMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return runSourceConnectionSync(token, orgId, sourceConnection.id);
    },
    onSuccess: () => {
      toast.success("Sync started");
      onConnectionUpdated?.();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to start sync"
      );
    },
  });

  // Cancel sync mutation
  const cancelSyncMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      if (currentSyncJob?.id) {
        return cancelSourceConnectionSync(
          token,
          orgId,
          sourceConnection.id,
          currentSyncJob.id
        );
      }
    },
    onSuccess: () => {
      toast.success("Cancellation requested");
      onConnectionUpdated?.();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to cancel sync"
      );
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return deleteSourceConnection(token, orgId, sourceConnection.id);
    },
    onSuccess: () => {
      toast.success("Source connection deleted");
      setShowDeleteDialog(false);
      queryClient.invalidateQueries({
        queryKey: queryKeys.sourceConnections.all(
          orgId,
          sourceConnection.readable_collection_id
        ),
      });
      onConnectionDeleted?.();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to delete source connection"
      );
    },
  });

  // Refresh auth URL handler
  const handleRefreshAuthUrl = useCallback(async () => {
    setIsRefreshingAuth(true);
    try {
      const token = await getAccessTokenSilently();
      await fetchSourceConnection(
        token,
        orgId,
        initialSourceConnection.id,
        true
      );
      toast.success("Authentication URL refreshed");
      queryClient.invalidateQueries({
        queryKey: queryKeys.sourceConnections.detail(
          orgId,
          initialSourceConnection.id
        ),
      });
      onConnectionUpdated?.();
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to refresh authentication URL"
      );
    } finally {
      setIsRefreshingAuth(false);
    }
  }, [
    getAccessTokenSilently,
    orgId,
    initialSourceConnection.id,
    queryClient,
    onConnectionUpdated,
  ]);

  const syncStatus = getSyncStatusDisplay(
    isNotAuthorized,
    isFederatedSource,
    syncState,
    jobStatus
  );
  const lastRanDisplay = formatTimeAgo(
    sourceConnection.last_sync_job?.started_at
  );

  const entityStates = sourceConnection.entities
    ? Object.entries(sourceConnection.entities.by_type).map(
        ([type, stats]) => ({
          entity_type: type,
          total_count: stats.count,
          last_updated_at: stats.last_updated,
          sync_status: stats.sync_status as
            | "pending"
            | "syncing"
            | "synced"
            | "failed",
        })
      )
    : [];

  // Show authorization UI if not authorized
  if (isNotAuthorized) {
    return (
      <>
        <SourceAuthenticationView
          sourceName={sourceConnection.name}
          sourceShortName={sourceConnection.short_name}
          authenticationUrl={sourceConnection.auth?.auth_url}
          onRefreshUrl={handleRefreshAuthUrl}
          isRefreshing={isRefreshingAuth}
          onDelete={() => setShowDeleteDialog(true)}
        />
        <DeleteSourceDialog
          open={showDeleteDialog}
          onOpenChange={setShowDeleteDialog}
          onConfirm={() => deleteMutation.mutate()}
          sourceName={sourceConnection.name}
          isDeleting={deleteMutation.isPending}
          hasData={false}
        />
      </>
    );
  }

  return (
    <div className="space-y-4">
      <SyncStatusDashboard
        isFederatedSource={isFederatedSource}
        syncState={syncState}
        isSyncing={isSyncing}
        entityCount={sourceConnection.entities?.total_entities || 0}
        statusDisplay={syncStatus}
        scheduleCron={sourceConnection.schedule?.cron}
        scheduleNextRun={sourceConnection.schedule?.next_run}
        lastSyncTime={lastRanDisplay}
        onSync={() => runSyncMutation.mutate()}
        onCancelSync={() => cancelSyncMutation.mutate()}
        onDelete={() => setShowDeleteDialog(true)}
        isSyncPending={runSyncMutation.isPending}
        isCancelPending={cancelSyncMutation.isPending}
      />

      {/* Error Card */}
      {!isFederatedSource && currentSyncJob?.status === "failed" && (
        <SyncErrorCard
          error={
            currentSyncJob.error ||
            "The last sync failed. Check the logs for more details."
          }
        />
      )}

      {/* Federated Search Info Card */}
      {isFederatedSource && <FederatedSearchInfo />}

      {/* Entity State List */}
      {!isFederatedSource && (
        <EntityStateList
          entityStates={entityStates}
          isRunning={isRunning}
          isPending={isPending}
          onStartSync={() => runSyncMutation.mutate()}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <DeleteSourceDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        onConfirm={() => deleteMutation.mutate()}
        sourceName={sourceConnection.name}
        isDeleting={deleteMutation.isPending}
        hasData={true}
      />
    </div>
  );
}
