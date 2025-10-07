// components/collection/SourceConnectionStateView.tsx
import React, { useEffect, useState, useRef, useCallback } from 'react';
import { EntityStateMediator } from '@/services/entityStateMediator';
import { useEntityStateStore } from '@/stores/entityStateStore';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { Loader2, AlertCircle, RefreshCw, Clock, X, History, Square, ExternalLink, Copy, Check, Send } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { toast } from '@/hooks/use-toast';
import { SourceConnectionSettings } from './SourceConnectionSettings';
import { EntityStateList } from './EntityStateList';
import { SyncErrorCard } from './SyncErrorCard';
import { SourceAuthenticationView } from '@/components/shared/SourceAuthenticationView';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { DESIGN_SYSTEM } from '@/lib/design-system';
import { useCollectionCreationStore } from '@/stores/collectionCreationStore';
import type { SingleActionCheckResponse } from '@/types';
import { useUsageStore } from '@/lib/stores/usage';
import { parseCronExpression, formatTimeUntil } from '@/utils/cronParser';

// Source Connection interface - matches backend schema
interface LastSyncJob {
  id?: string;
  status?: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  entities_inserted?: number;
  entities_updated?: number;
  entities_deleted?: number;
  entities_failed?: number;
  error?: string;
  error_details?: Record<string, any>;
}

interface Schedule {
  cron?: string;  // Backend uses 'cron', not 'cron_expression'
  next_run?: string;  // Backend uses 'next_run', not 'next_run_at'
  continuous?: boolean;  // Backend uses 'continuous', not 'is_continuous'
  cursor_field?: string;
  cursor_value?: any;
}

interface AuthenticationInfo {
  method?: string;
  authenticated?: boolean;  // Backend uses 'authenticated', not 'is_authenticated'
  authenticated_at?: string;
  expires_at?: string;
  auth_url?: string;  // Backend uses 'auth_url', not 'authentication_url'
  auth_url_expires?: string;  // Backend uses 'auth_url_expires'
  provider_id?: string;  // Backend uses 'provider_id'
  provider_readable_id?: string;  // Backend uses 'provider_readable_id'
  redirect_url?: string;
}

interface EntityTypeStats {
  count: number;
  last_updated?: string;
  sync_status: string;
}

interface EntitySummary {
  total_entities: number;
  by_type: Record<string, EntityTypeStats>;
  last_updated?: string;
}

interface SourceConnection {
  id: string;
  name: string;
  description?: string;
  short_name: string;
  readable_collection_id: string;
  status?: string;
  created_at: string;
  modified_at: string;
  // Authentication is now in the auth object
  auth?: AuthenticationInfo;  // Contains authenticated, method, etc.
  config?: Record<string, any>;  // Changed from config_fields
  schedule?: Schedule;
  sync?: {
    last_job?: LastSyncJob;
    total_runs?: number;
    successful_runs?: number;
    failed_runs?: number;
  };
  entities?: EntitySummary;  // Changed from entity_states array to entities object
  // Legacy fields that may still exist
  sync_id?: string;
  organization_id?: string;
  connection_id?: string;
  created_by_email?: string;
  modified_by_email?: string;
}

interface Props {
  sourceConnectionId: string;
  sourceConnectionData?: SourceConnection;  // Accept data as prop
  onConnectionDeleted?: () => void;
  onConnectionUpdated?: () => void;  // Callback to refresh data in parent
  collectionId?: string;  // Collection ID for opening add source flow
  collectionName?: string;  // Collection name for opening add source flow
}

const SourceConnectionStateView: React.FC<Props> = ({
  sourceConnectionId,
  sourceConnectionData,
  onConnectionDeleted,
  onConnectionUpdated,
  collectionId,
  collectionName
}) => {
  const [isInitializing, setIsInitializing] = useState(true);
  const [sourceConnection, setSourceConnection] = useState<SourceConnection | null>(sourceConnectionData || null);
  const [lastRanDisplay, setLastRanDisplay] = useState<string | null>(null);
  const [isRefreshingAuth, setIsRefreshingAuth] = useState(false);

  // Track if we initiated a cancellation (for timeout handling)
  const [isLocalCancelling, setIsLocalCancelling] = useState(false);
  const cancelTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  // Use usage store for limits
  const actionChecks = useUsageStore(state => state.actionChecks);
  const isCheckingUsage = useUsageStore(state => state.isLoading);
  const entitiesAllowed = actionChecks.entities?.allowed ?? true;
  const entitiesCheckDetails = actionChecks.entities;
  const sourceConnectionsAllowed = actionChecks.source_connections?.allowed ?? true;
  const sourceConnectionsCheckDetails = actionChecks.source_connections;

  const mediator = useRef<EntityStateMediator | null>(null);
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  // Direct store subscription - single source of truth for real-time updates
  const storeConnection = useEntityStateStore(
    store => store.getConnection(sourceConnectionId)
  );

  // Use source connection data as primary source, with store for real-time updates
  const connectionState = sourceConnection || storeConnection;

  // Format time ago display
  const formatTimeAgo = useCallback((dateStr: string | undefined) => {
    if (!dateStr) return null;  // Return null instead of 'Never'

    // CRITICAL: Backend sends naive datetime strings WITHOUT timezone
    // These are actually UTC times but JavaScript interprets them as LOCAL time by default!
    // Check if it already has timezone info (Z, +, or - but not in the date part like 2024-01-15)
    const hasTimezone = dateStr.endsWith('Z') ||
      dateStr.match(/[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:?\d{2}$/);

    const utcDateStr = hasTimezone ? dateStr : `${dateStr}Z`;

    const date = new Date(utcDateStr);
    const now = new Date();

    // Now both dates are properly parsed and comparison is correct
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays > 0) {
      return `${diffDays}d ago`;
    } else if (diffHrs > 0) {
      return `${diffHrs}h ago`;
    } else if (diffMins > 0) {
      return `${diffMins}m ago`;
    } else {
      return 'Just now';
    }
  }, []);

  // Format exact timestamp for tooltip
  const formatExactTime = useCallback((dateStr: string | undefined) => {
    if (!dateStr) return null;

    // Backend sends naive datetime strings that are actually UTC
    // We need to interpret them as UTC, not local time
    const hasTimezone = dateStr.endsWith('Z') ||
      dateStr.match(/[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:?\d{2}$/);

    const utcDateStr = hasTimezone ? dateStr : `${dateStr}Z`;

    const date = new Date(utcDateStr);

    // Format in user's local timezone with clear indication
    const localTime = date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short'
    });

    // Also show UTC time for clarity
    const utcTime = date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZone: 'UTC',
      timeZoneName: 'short'
    });

    // Return both times if they're different
    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (userTimezone === 'UTC') {
      return localTime;
    } else {
      return `${localTime}`;  // Just show local time, it already includes timezone
    }
  }, []);


  // Fetch source connection details (only when not provided as prop)
  const fetchSourceConnection = useCallback(async (regenerateAuthUrl = false) => {
    try {
      const url = regenerateAuthUrl
        ? `/source-connections/${sourceConnectionId}?regenerate_auth_url=true`
        : `/source-connections/${sourceConnectionId}`;
      const response = await apiClient.get(url);
      if (response.ok) {
        const data = await response.json();
        setSourceConnection(data);

        // Update the store with fresh data
        if (data.sync?.last_job?.id) {
          const storeState = {
            id: data.id,
            name: data.name,
            short_name: data.short_name,
            collection: data.readable_collection_id,
            status: (data.status as any) || 'active',
            is_authenticated: data.auth?.authenticated ?? true,
            last_sync_job: {
              ...data.sync.last_job,
              id: data.sync.last_job.id!
            },
            schedule: data.schedule,
            entity_states: data.entities ?
              Object.entries(data.entities.by_type).map(([type, stats]) => ({
                entity_type: type,
                total_count: (stats as any).count,
                last_updated_at: (stats as any).last_updated,
                sync_status: (stats as any).sync_status
              })) : [],
            lastUpdated: new Date()
          };
          useEntityStateStore.getState().setSourceConnection(storeState as any);
        }
      }
    } catch (error) {
      console.error('Failed to fetch source connection:', error);
    }
  }, [sourceConnectionId]);

  // Handler for refreshing authentication URL
  const handleRefreshAuthUrl = useCallback(async () => {
    setIsRefreshingAuth(true);
    try {
      await fetchSourceConnection(true);
      toast({
        title: "Refreshed",
        description: "Authentication URL has been refreshed"
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to refresh authentication URL",
        variant: "destructive"
      });
    } finally {
      setIsRefreshingAuth(false);
    }
  }, [fetchSourceConnection]);

  useEffect(() => {
    const isNotAuthorized = sourceConnectionData?.status === 'pending_auth' || !sourceConnectionData?.auth?.authenticated;

    // Only initialize mediator if authenticated
    if (!isNotAuthorized) {
      mediator.current = new EntityStateMediator(sourceConnectionId);

      // If we have source connection data, update the store immediately
      if (sourceConnectionData && sourceConnectionData.sync?.last_job?.id) {
        const storeState = {
          id: sourceConnectionData.id,
          name: sourceConnectionData.name,
          short_name: sourceConnectionData.short_name,
          collection: sourceConnectionData.readable_collection_id,
          status: (sourceConnectionData.status as any) || 'active',  // Cast to bypass type check
          is_authenticated: sourceConnectionData.auth?.authenticated ?? true,
          last_sync_job: sourceConnectionData.sync.last_job ? {
            ...sourceConnectionData.sync.last_job,
            id: sourceConnectionData.sync.last_job.id!  // Ensure id is not undefined
          } : undefined,
          schedule: sourceConnectionData.schedule,
          entity_states: sourceConnectionData.entities ?
            Object.entries(sourceConnectionData.entities.by_type).map(([type, stats]) => ({
              entity_type: type,
              total_count: stats.count,
              last_updated_at: stats.last_updated,
              sync_status: stats.sync_status as any
            })) : [],
          lastUpdated: new Date()
        };
        useEntityStateStore.getState().setSourceConnection(storeState as any);
      }

      Promise.all([
        mediator.current.initialize(),
        fetchSourceConnection()
      ]).then(async () => {
        setIsInitializing(false);

        // Check the store for active sync job after initialization
        const currentState = useEntityStateStore.getState().getConnection(sourceConnectionId);
        if (currentState?.last_sync_job?.id &&
          ((currentState.last_sync_job.status as any) === 'running' ||
            currentState.last_sync_job.status === 'in_progress' ||
            currentState.last_sync_job.status === 'pending' ||
            currentState.last_sync_job.status === 'created' ||
            currentState.last_sync_job.status === 'cancelling')) {
          await mediator.current.subscribeToJobUpdates(currentState.last_sync_job.id);
        }
      }).catch(error => {
        console.error('Failed to initialize:', error);
        setIsInitializing(false);
      });
    } else {
      // Just fetch connection details if not authenticated
      fetchSourceConnection().then(() => {
        setIsInitializing(false);
      }).catch(error => {
        console.error('Failed to fetch connection:', error);
        setIsInitializing(false);
      });
    }

    return () => {
      mediator.current?.cleanup();
      // Clean up any pending timeout
      if (cancelTimeoutRef.current) {
        clearTimeout(cancelTimeoutRef.current);
        cancelTimeoutRef.current = null;
      }
    };
  }, [sourceConnectionId, sourceConnectionData?.status, sourceConnectionData?.auth?.authenticated]); // Add auth status to deps

  // Update source connection when prop changes
  useEffect(() => {
    if (sourceConnectionData && sourceConnectionData !== sourceConnection) {
      setSourceConnection(sourceConnectionData);
    }
  }, [sourceConnectionData]);


  // Update last ran display
  useEffect(() => {
    const updateLastRan = () => {
      // Don't show "Running now" - let the status badge handle that
      const startedAt = storeConnection?.last_sync_job?.started_at || sourceConnection?.sync?.last_job?.started_at;
      setLastRanDisplay(formatTimeAgo(startedAt));
    };

    updateLastRan();
    // Update every minute to keep the display fresh
    const interval = setInterval(updateLastRan, 60000);

    return () => clearInterval(interval);
  }, [storeConnection?.last_sync_job?.started_at, sourceConnection?.sync?.last_job?.started_at, formatTimeAgo]);


  // Clear local cancelling state when appropriate
  useEffect(() => {
    const syncStatus = storeConnection?.last_sync_job?.status;

    if (isLocalCancelling) {
      // Clear when:
      // 1. Backend confirms cancelling status (we can rely on backend now)
      // 2. Job reaches a final state
      // 3. Status is not a running state (means job ended or never started)
      if (syncStatus === 'cancelling' ||
        syncStatus === 'cancelled' ||
        syncStatus === 'completed' ||
        syncStatus === 'failed' ||
        (!syncStatus || (syncStatus !== 'running' && syncStatus !== 'in_progress' && syncStatus !== 'pending' && syncStatus !== 'created'))) {
        setIsLocalCancelling(false);
        if (cancelTimeoutRef.current) {
          clearTimeout(cancelTimeoutRef.current);
          cancelTimeoutRef.current = null;
        }
      }
    }
  }, [storeConnection?.last_sync_job?.status, isLocalCancelling]);

  // Refetch source connection when sync fails to get latest error details
  useEffect(() => {
    const syncStatus = storeConnection?.last_sync_job?.status;
    const error = storeConnection?.last_sync_job?.error;
    if (syncStatus === 'failed' || error) {
      // Refetch to get the last_sync_job.error from backend
      fetchSourceConnection();
    }
  }, [storeConnection?.last_sync_job?.status, storeConnection?.last_sync_job?.error, fetchSourceConnection]);

  // Refetch on completion or cancellation to refresh counts and latest job
  useEffect(() => {
    const syncStatus = storeConnection?.last_sync_job?.status;
    if (syncStatus === 'completed' || syncStatus === 'cancelled' || syncStatus === 'failed') {
      fetchSourceConnection();
    }
  }, [storeConnection?.last_sync_job?.status, fetchSourceConnection]);

  // Usage limits are checked at app level by UsageChecker component

  const handleRunSync = async () => {
    if (!entitiesAllowed || isCheckingUsage) {
      toast({
        title: "Limit reached",
        description: entitiesCheckDetails?.reason === 'usage_limit_exceeded'
          ? "Entity processing limit reached. Upgrade your plan to continue syncing."
          : "Sync is currently blocked by billing status.",
        variant: 'destructive'
      });
      return;
    }

    // Clear any lingering cancellation state
    setIsLocalCancelling(false);
    if (cancelTimeoutRef.current) {
      clearTimeout(cancelTimeoutRef.current);
      cancelTimeoutRef.current = null;
    }

    try {
      const response = await apiClient.post(`/source-connections/${sourceConnectionId}/run`);
      if (response.ok) {
        const syncJob = await response.json();
        toast({
          title: "Sync started",
          description: "The sync has been started successfully"
        });

        // Let the mediator handle the state transition
        if (mediator.current && syncJob.id) {
          await mediator.current.subscribeToJobUpdates(syncJob.id);
        }
      } else {
        throw new Error("Failed to start sync");
      }
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to start sync",
        variant: "destructive"
      });
    }
  };

  const handleCancelSync = async () => {
    const jobId = storeConnection?.last_sync_job?.id || sourceConnection?.sync?.last_job?.id;

    if (!jobId) {
      return;
    }

    // Set cancelling state immediately for instant UI feedback
    setIsLocalCancelling(true);

    // Clear any existing timeout
    if (cancelTimeoutRef.current) {
      clearTimeout(cancelTimeoutRef.current);
      cancelTimeoutRef.current = null;
    }

    try {
      // Set a 30-second timeout for cancellation
      cancelTimeoutRef.current = setTimeout(() => {
        setIsLocalCancelling(false);
        toast({
          title: "Cancellation Timeout",
          description: "The cancellation request timed out. The sync may still be cancelled in the background.",
          variant: "destructive"
        });
        cancelTimeoutRef.current = null;
      }, 30000);

      const response = await apiClient.post(`/source-connections/${sourceConnectionId}/jobs/${jobId}/cancel`);

      if (response.ok) {
        toast({
          title: "Cancellation Requested",
          description: "The sync is being cancelled. This may take a moment to complete.",
        });
        // Don't clear isLocalCancelling here - let the status change clear it
      } else {
        const errorText = await response.text();
        throw new Error(errorText || "Failed to cancel sync job");
      }
    } catch (error) {
      // Clear on error
      setIsLocalCancelling(false);
      if (cancelTimeoutRef.current) {
        clearTimeout(cancelTimeoutRef.current);
        cancelTimeoutRef.current = null;
      }
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to cancel sync job",
        variant: "destructive"
      });
    }
  };

  const handleConnectionUpdate = (updatedConnection: SourceConnection) => {
    setSourceConnection(updatedConnection);
    // Re-fetch to ensure everything is in sync
    fetchSourceConnection();
  };

  const handleDeleteConnection = async () => {
    if (!sourceConnection) return;

    try {
      const response = await apiClient.delete(`/source-connections/${sourceConnection.id}`);

      if (!response.ok) {
        const error = await response.text();
        throw new Error(error || 'Failed to delete source connection');
      }

      toast({
        title: "Source connection deleted",
        description: "The source connection has been permanently deleted.",
      });

      // Call the parent callback to handle the deletion
      if (onConnectionDeleted) {
        onConnectionDeleted();
      }

      // Open the add source flow if collection info is available
      if (collectionId && collectionName) {
        const store = useCollectionCreationStore.getState();
        store.openForAddToCollection(collectionId, collectionName);
      }
    } catch (error) {
      console.error('Error deleting source connection:', error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete source connection",
        variant: "destructive"
      });
    }
  };

  if (isInitializing && !connectionState) {
    return (
      <div className="w-full h-48 flex flex-col items-center justify-center space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className={cn(DESIGN_SYSTEM.typography.sizes.body, "text-muted-foreground")}>Loading entity state...</p>
      </div>
    );
  }

  // Derive sync state from job status - single source of truth
  const currentSyncJob = storeConnection?.last_sync_job || sourceConnection?.sync?.last_job;
  const jobStatus = currentSyncJob?.status as unknown as string | undefined;

  // Simple state machine: IDLE | SYNCING | CANCELLING
  // FORCE CANCELLING STATE when isLocalCancelling is true
  let syncState: 'IDLE' | 'SYNCING' | 'CANCELLING' = 'IDLE';
  if (isLocalCancelling) {
    // ALWAYS show cancelling if we clicked the button
    syncState = 'CANCELLING';
  } else if (jobStatus === 'cancelling') {
    syncState = 'CANCELLING';
  } else if (jobStatus === 'running' || jobStatus === 'in_progress' || jobStatus === 'pending' || jobStatus === 'created') {
    syncState = 'SYNCING';
  }

  // Legacy flags for compatibility
  const isRunning = jobStatus === 'running' || jobStatus === 'in_progress';
  const isPending = currentSyncJob?.status === 'pending' || currentSyncJob?.status === 'created';
  const isCancellingStatus = jobStatus === 'cancelling';
  const isCancelledStatus = currentSyncJob?.status === 'cancelled';
  const isSyncing = syncState !== 'IDLE';

  // Get sync status display
  const getSyncStatusDisplay = () => {
    if (sourceConnection?.status === 'pending_auth' || !sourceConnection?.auth?.authenticated) {
      return { text: 'Not Authenticated', color: 'bg-cyan-500', icon: null };
    }
    if (syncState === 'CANCELLING') return { text: 'Cancelling', color: 'bg-orange-500 animate-pulse', icon: 'loader' };
    if (currentSyncJob?.status === 'failed') return { text: 'Failed', color: 'bg-red-500', icon: null };
    if (currentSyncJob?.status === 'completed') return { text: 'Completed', color: 'bg-green-500', icon: null };
    if (currentSyncJob?.status === 'cancelled') return { text: 'Cancelled', color: 'bg-gray-500', icon: null };
    if (isRunning) return { text: 'Syncing', color: 'bg-blue-500 animate-pulse', icon: 'loader' };
    if (isPending) return { text: 'Pending', color: 'bg-yellow-500 animate-pulse', icon: 'loader' };
    return { text: 'Ready', color: 'bg-gray-400', icon: null };
  };

  const syncStatus = getSyncStatusDisplay();
  const isNotAuthorized = sourceConnection?.status === 'pending_auth' || !sourceConnection?.auth?.authenticated;

  return (
    <div className={cn("space-y-4", DESIGN_SYSTEM.typography.sizes.body)}>
      {/* Show authorization UI if not authorized */}
      {isNotAuthorized && sourceConnection && (
        <SourceAuthenticationView
          sourceName={sourceConnection.name}
          sourceShortName={sourceConnection.short_name}
          authenticationUrl={sourceConnection.auth?.auth_url}
          onRefreshUrl={handleRefreshAuthUrl}
          isRefreshing={isRefreshingAuth}
          showBorder={false}
          onDelete={handleDeleteConnection}
        />
      )}

      {/* Status Dashboard with Settings - Only show when authenticated */}
      {!isNotAuthorized && (
        <div className="flex items-center justify-between">
          <div className="flex gap-2 flex-wrap items-center">
            {/* Entities Card */}
            <div className={cn("h-8 px-3 py-1.5 border border-border rounded-md shadow-sm flex items-center gap-2 min-w-[90px]", isDark ? "bg-gray-900" : "bg-white")}>
              <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">ENTITIES</span>
              <span className="text-xs font-semibold text-foreground">
                {/* Calculate total from real-time store data or fall back to source connection */}
                {(
                  storeConnection?.entity_states?.reduce((sum, state) => sum + (state.total_count || 0), 0) ||
                  sourceConnection?.entities?.total_entities ||
                  0
                ).toLocaleString()}
              </span>
            </div>

            {/* Status Card */}
            <div className={cn(
              "group relative h-8 px-3 py-1.5 rounded-lg border transition-all duration-200 flex items-center gap-2 min-w-[90px] hover:shadow-md",
              // Highlight when sync is running
              (isRunning || isPending || isCancellingStatus)
                ? isDark
                  ? "bg-gradient-to-r from-blue-900/40 to-blue-800/30 border-blue-700/60 hover:border-blue-600/60"
                  : "bg-gradient-to-r from-blue-50 to-blue-100/50 border-blue-200/60 hover:border-blue-300/60"
                : isDark
                  ? "bg-gradient-to-r from-slate-800/80 to-slate-900/80 border-slate-700/50 hover:border-slate-600/50"
                  : "bg-gradient-to-r from-slate-50 to-white border-slate-200/60 hover:border-slate-300/60"
            )}>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">STATUS</span>
              <div className="flex items-center gap-1.5">
                {syncStatus.icon === 'loader' ? (
                  <Loader2 className="h-3 w-3 animate-spin text-blue-500" />
                ) : (
                  <span className={`inline-flex h-2 w-2 rounded-full ${syncStatus.color}`} />
                )}
                <span className={cn(
                  "text-xs font-medium capitalize",
                  (isRunning || isPending) ? "text-blue-600 dark:text-blue-400" : "text-foreground"
                )}>{syncStatus.text}</span>
              </div>
            </div>

            {/* Schedule Card */}
            <TooltipProvider delayDuration={200}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className={cn(
                    "group relative h-8 px-3 py-1.5 rounded-lg border transition-all duration-200 flex items-center gap-2 min-w-[100px] cursor-help hover:shadow-md",
                    isDark
                      ? "bg-gradient-to-r from-slate-800/80 to-slate-900/80 border-slate-700/50 hover:border-slate-600/50"
                      : "bg-gradient-to-r from-slate-50 to-white border-slate-200/60 hover:border-slate-300/60"
                  )}>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">SCHEDULE</span>
                    <div className="flex items-center gap-1.5">
                      <Clock className="h-3 w-3 text-blue-500 dark:text-blue-400" />
                      <span className="text-xs font-medium text-foreground">
                        {(() => {
                          const parsed = parseCronExpression(sourceConnection?.schedule?.cron);
                          if (parsed) {
                            const nextRunStr = formatTimeUntil(sourceConnection?.schedule?.next_run);
                            return nextRunStr ? `${parsed.shortDescriptionLocal} (${nextRunStr})` : parsed.shortDescriptionLocal;
                          }
                          return 'Manual';
                        })()}
                      </span>
                    </div>
                    {/* Subtle indicator for live sync */}
                    {(() => {
                      const parsed = parseCronExpression(sourceConnection?.schedule?.cron);
                      return parsed && parsed.shortDescriptionLocal.includes('minute') ? (
                        <div className="absolute -top-1 -right-1 w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                      ) : null;
                    })()}
                  </div>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs p-3">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-blue-500" />
                      <p className="font-semibold text-sm">
                        {(() => {
                          const parsed = parseCronExpression(sourceConnection?.schedule?.cron);
                          return parsed ? parsed.descriptionLocal : 'Manual sync only';
                        })()}
                      </p>
                    </div>

                    {(() => {
                      const parsed = parseCronExpression(sourceConnection?.schedule?.cron);
                      return parsed && parsed.description !== parsed.descriptionLocal ? (
                        <p className="text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded">
                          UTC: {parsed.description}
                        </p>
                      ) : null;
                    })()}

                    {sourceConnection?.schedule?.next_run && (
                      <div className="pt-1 border-t border-border/50">
                        <p className="text-xs font-medium text-muted-foreground mb-1">Next sync:</p>
                        <p className="text-xs text-foreground">
                          {new Date(sourceConnection.schedule.next_run).toLocaleString()} UTC
                        </p>
                      </div>
                    )}

                    {sourceConnection?.schedule?.cron && (
                      <div className="pt-1 border-t border-border/50">
                        <p className="text-xs font-medium text-muted-foreground mb-1">Cron expression:</p>
                        <code className="text-xs font-mono bg-muted/50 px-2 py-1 rounded block">
                          {sourceConnection.schedule.cron}
                        </code>
                      </div>
                    )}
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {/* Last Sync Card - Enhanced with entity stats */}
            {!(isRunning || isPending || isCancellingStatus) && lastRanDisplay && (
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className={cn(
                      "group relative h-8 px-3 py-1.5 rounded-lg border transition-all duration-200 flex items-center gap-2 min-w-[100px] cursor-help hover:shadow-md",
                      isDark
                        ? "bg-gradient-to-r from-slate-800/80 to-slate-900/80 border-slate-700/50 hover:border-slate-600/50"
                        : "bg-gradient-to-r from-slate-50 to-white border-slate-200/60 hover:border-slate-300/60"
                    )}>
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">LAST SYNC</span>
                      <div className="flex items-center gap-1.5">
                        <History className="h-3 w-3 text-green-500 dark:text-green-400" />
                        <span className="text-xs font-medium text-foreground">
                          {lastRanDisplay}
                        </span>
                      </div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs p-3">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <History className="h-4 w-4 text-green-500" />
                        <p className="font-semibold text-sm">
                          {formatExactTime(sourceConnection?.sync?.last_job?.started_at) ||
                            formatExactTime(sourceConnection?.sync?.last_job?.completed_at) ||
                            'Last sync time unavailable'}
                        </p>
                      </div>

                      {sourceConnection?.sync?.last_job ? (
                        <div className="pt-1 border-t border-border/50">
                          <p className="text-xs font-medium text-muted-foreground mb-1">Sync results:</p>
                          <div className="text-xs space-y-1">
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Inserted:</span>
                              <span className="font-medium text-green-600 dark:text-green-400">
                                {sourceConnection.sync.last_job.entities_inserted || 0}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Updated:</span>
                              <span className="font-medium text-blue-600 dark:text-blue-400">
                                {sourceConnection.sync.last_job.entities_updated || 0}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Deleted:</span>
                              <span className="font-medium text-red-600 dark:text-red-400">
                                {sourceConnection.sync.last_job.entities_deleted || 0}
                              </span>
                            </div>
                            {sourceConnection.sync.last_job.duration_seconds && (
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Duration:</span>
                                <span className="font-medium">
                                  {sourceConnection.sync.last_job.duration_seconds}s
                                </span>
                              </div>
                            )}
                            {sourceConnection.sync.last_job.status && (
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Status:</span>
                                <span className="font-medium capitalize">
                                  {sourceConnection.sync.last_job.status}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                      ) : (
                        <div className="pt-1 border-t border-border/50">
                          <p className="text-xs text-muted-foreground">
                            No sync job data available
                          </p>
                        </div>
                      )}
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>

          {/* Settings and Action Buttons */}
          <div className="flex gap-1.5 items-center">
            {/* Refresh/Cancel Button */}
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={() => {
                      if (syncState === 'IDLE') {
                        if (!entitiesAllowed || isCheckingUsage) return;
                        handleRunSync();
                      } else if (syncState === 'SYNCING') {
                        handleCancelSync();
                      }
                      // Do nothing if CANCELLING
                    }}
                    disabled={syncState === 'CANCELLING' || (!entitiesAllowed && syncState === 'IDLE')}
                    className={cn(
                      "h-8 w-8 rounded-md border shadow-sm flex items-center justify-center transition-all duration-200",
                      syncState !== 'IDLE'
                        ? syncState === 'CANCELLING'
                          ? isDark
                            ? "bg-orange-900/30 border-orange-700 hover:bg-orange-900/50 cursor-not-allowed"
                            : "bg-orange-50 border-orange-200 hover:bg-orange-100 cursor-not-allowed"
                          : isDark
                            ? "bg-red-900/30 border-red-700 hover:bg-red-900/50 cursor-pointer"
                            : "bg-red-50 border-red-200 hover:bg-red-100 cursor-pointer"
                        : (!entitiesAllowed && syncState === 'IDLE') || isCheckingUsage
                          ? "bg-muted border-border cursor-not-allowed opacity-50"
                          : isDark
                            ? "bg-gray-900 border-border hover:bg-muted cursor-pointer"
                            : "bg-white border-border hover:bg-muted cursor-pointer"
                    )}
                    title={syncState === 'CANCELLING' ? "Cancelling sync..." : syncState === 'SYNCING' ? "Cancel sync" : (!entitiesAllowed ? "Entity limit reached" : "Refresh data")}
                  >
                    {syncState === 'CANCELLING' ? (
                      <Loader2 className="h-3 w-3 animate-spin text-orange-500" />
                    ) : syncState === 'SYNCING' ? (
                      <Square className="h-3 w-3 text-red-500" />
                    ) : (
                      <RefreshCw className="h-3 w-3 text-muted-foreground" />
                    )}
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">
                    {syncState === 'CANCELLING'
                      ? "Cancelling sync..."
                      : syncState === 'SYNCING'
                        ? "Cancel sync"
                        : !entitiesAllowed && entitiesCheckDetails?.reason === 'usage_limit_exceeded'
                          ? "Entity processing limit reached. Upgrade your plan to sync more data."
                          : !entitiesAllowed && entitiesCheckDetails?.reason === 'payment_required'
                            ? "Billing issue detected. Update billing to sync data."
                            : "Refresh data"}
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {/* Settings Menu */}
            {sourceConnection && (
              <div className={cn("h-8 w-8 border border-border rounded-md shadow-sm flex items-center justify-center", isDark ? "bg-gray-900" : "bg-white")}>
                <button
                  type="button"
                  onClick={() => {/* Settings menu trigger logic would go here */ }}
                  className="h-8 w-8 flex items-center justify-center hover:bg-muted rounded-md transition-all duration-200"
                  title="Settings"
                >
                  <SourceConnectionSettings
                    sourceConnection={sourceConnection as any}
                    onUpdate={handleConnectionUpdate as any}
                    onDelete={onConnectionDeleted}
                    isDark={isDark}
                    resolvedTheme={resolvedTheme}
                  />
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Only show sync-related UI when authenticated */}
      {!isNotAuthorized && (
        <>
          {/* Show error card if sync failed or there's an error */}
          {(currentSyncJob?.status === 'failed') && (
            <SyncErrorCard
              error={currentSyncJob?.error || sourceConnection?.sync?.last_job?.error || "The last sync failed. Check the logs for more details."}
              isDark={isDark}
            />
          )}

          {/* Show Entity State List only when authenticated */}
          <EntityStateList
            state={storeConnection}  // Pass store connection for real-time updates
            sourceShortName={sourceConnection?.short_name || ''}
            isDark={isDark}
            onStartSync={handleRunSync}
            isRunning={isRunning}
            isPending={isPending}
            entityStates={sourceConnection?.entities ?
              Object.entries(sourceConnection.entities.by_type).map(([type, stats]) => ({
                entity_type: type,
                total_count: stats.count,
                last_updated_at: stats.last_updated,
                sync_status: stats.sync_status as 'pending' | 'syncing' | 'synced' | 'failed'
              })) : undefined}  // Convert entities to entity_states format for EntityStateList
          />
        </>
      )}
    </div>
  );
};

export default SourceConnectionStateView;
