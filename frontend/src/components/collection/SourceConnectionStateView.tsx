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

// Source Connection interface - matches backend schema
interface LastSyncJob {
  id?: string;
  status?: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  entities_processed?: number;
  entities_inserted?: number;
  entities_updated?: number;
  entities_deleted?: number;
  entities_failed?: number;
  error?: string;
  error_details?: Record<string, any>;
}

interface Schedule {
  cron_expression?: string;
  next_run_at?: string;
  is_continuous?: boolean;
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
  provider_name?: string;  // Backend uses 'provider_name'
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
  last_sync_job?: LastSyncJob;
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
}

const SourceConnectionStateView: React.FC<Props> = ({
  sourceConnectionId,
  sourceConnectionData,
  onConnectionDeleted,
  onConnectionUpdated
}) => {
  const [isInitializing, setIsInitializing] = useState(true);
  const [sourceConnection, setSourceConnection] = useState<SourceConnection | null>(sourceConnectionData || null);
  const [isRunningSync, setIsRunningSync] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [nextRunTime, setNextRunTime] = useState<string | null>(null);
  const [lastRanDisplay, setLastRanDisplay] = useState<string>('Never');
  const [isRefreshingAuth, setIsRefreshingAuth] = useState(false);

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
    if (!dateStr) return 'Never';

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
    if (!dateStr) return 'Never';

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

  // Calculate next run time from cron expression
  const calculateNextRunTime = useCallback((cronExpression: string | null) => {
    if (!cronExpression) return null;

    try {
      const parts = cronExpression.split(' ');
      if (parts.length !== 5) return null;

      const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;
      const now = new Date();

      // Create next run date in UTC since cron expressions are typically in UTC
      const nextRun = new Date(now);

      // Simplified calculation for daily schedules
      if (hour !== '*' && dayOfMonth === '*' && dayOfWeek === '*') {
        const targetHour = parseInt(hour);
        const targetMinute = parseInt(minute) || 0;

        // Set the UTC time for next run
        nextRun.setUTCHours(targetHour, targetMinute, 0, 0);

        // If the time has already passed today, move to tomorrow
        if (nextRun <= now) {
          nextRun.setUTCDate(nextRun.getUTCDate() + 1);
        }
      }

      // Calculate time difference from now
      const diffMs = nextRun.getTime() - now.getTime();
      const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
      const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

      if (diffHrs > 0) {
        return `${diffHrs}h ${diffMins}m`;
      } else if (diffMins > 0) {
        return `${diffMins}m`;
      } else {
        return 'Soon';
      }
    } catch (error) {
      console.error("Error calculating next run time:", error);
      return null;
    }
  }, []);

  // Fetch source connection details (only when not provided as prop)
  const fetchSourceConnection = useCallback(async (regenerateAuthUrl = false) => {
    // If data is provided as prop, use it instead of fetching
    if (sourceConnectionData) {
      setSourceConnection(sourceConnectionData);
      // Calculate next run time
      if (sourceConnectionData.schedule?.cron_expression) {
        const nextRun = calculateNextRunTime(sourceConnectionData.schedule.cron_expression);
        setNextRunTime(nextRun);
      }
      return;
    }

    try {
      const url = regenerateAuthUrl
        ? `/source-connections/${sourceConnectionId}?regenerate_auth_url=true`
        : `/source-connections/${sourceConnectionId}`;
      const response = await apiClient.get(url);
      if (response.ok) {
        const data = await response.json();
        setSourceConnection(data);

        // Calculate next run time
        if (data.schedule?.cron_expression) {
          const nextRun = calculateNextRunTime(data.schedule.cron_expression);
          setNextRunTime(nextRun);
        }

        // No need for separate auth URL fetch, it's handled by the regenerateAuthUrl parameter
      }
    } catch (error) {
      console.error('Failed to fetch source connection:', error);
    }
  }, [sourceConnectionId, sourceConnectionData, calculateNextRunTime]);

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
    const isNotAuthorized = sourceConnectionData?.status === 'not_yet_authorized' || !sourceConnectionData?.auth?.authenticated;

    // Only initialize mediator if authenticated
    if (!isNotAuthorized) {
      mediator.current = new EntityStateMediator(sourceConnectionId);

      // If we have source connection data, update the store immediately
      if (sourceConnectionData && sourceConnectionData.last_sync_job?.id) {
        const storeState = {
          id: sourceConnectionData.id,
          name: sourceConnectionData.name,
          short_name: sourceConnectionData.short_name,
          collection: sourceConnectionData.readable_collection_id,
          status: (sourceConnectionData.status as any) || 'active',  // Cast to bypass type check
          is_authenticated: sourceConnectionData.auth?.authenticated ?? true,
          last_sync_job: sourceConnectionData.last_sync_job ? {
            ...sourceConnectionData.last_sync_job,
            id: sourceConnectionData.last_sync_job.id!  // Ensure id is not undefined
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
            (currentState.last_sync_job.status === 'in_progress' ||
             currentState.last_sync_job.status === 'pending' ||
             currentState.last_sync_job.status === 'created')) {
          console.log('Subscribing to active sync job:', currentState.last_sync_job.id);
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
    };
  }, [sourceConnectionId, sourceConnectionData?.status, sourceConnectionData?.auth?.authenticated]); // Add auth status to deps

  // Update source connection when prop changes
  useEffect(() => {
    if (sourceConnectionData && sourceConnectionData !== sourceConnection) {
      setSourceConnection(sourceConnectionData);
      // Calculate next run time
      if (sourceConnectionData.schedule?.cron_expression) {
        const nextRun = calculateNextRunTime(sourceConnectionData.schedule.cron_expression);
        setNextRunTime(nextRun);
      }
    }
  }, [sourceConnectionData, calculateNextRunTime]);

  // Update next run time when schedule changes
  useEffect(() => {
    if (sourceConnection?.schedule?.cron_expression) {
      const nextRun = calculateNextRunTime(sourceConnection.schedule.cron_expression);
      setNextRunTime(nextRun);
    } else {
      setNextRunTime(null);
    }
  }, [sourceConnection?.schedule?.cron_expression, calculateNextRunTime]);

  // Update last ran display
  useEffect(() => {
    const updateLastRan = () => {
      // Don't show "Running now" - let the status badge handle that
      if (sourceConnection?.last_sync_job?.started_at) {
        setLastRanDisplay(formatTimeAgo(sourceConnection.last_sync_job.started_at));
      } else {
        setLastRanDisplay('Never');
      }
    };

    updateLastRan();
    // Update every minute to keep the display fresh
    const interval = setInterval(updateLastRan, 60000);

    return () => clearInterval(interval);
  }, [sourceConnection?.last_sync_job?.started_at, formatTimeAgo]);

  // Clear cancelling state when sync status changes to cancelled
  useEffect(() => {
    const syncStatus = storeConnection?.last_sync_job?.status;
    if (syncStatus === 'cancelled' && isCancelling) {
      setIsCancelling(false);
      toast({
        title: "Sync Cancelled",
        description: "The sync job has been successfully cancelled.",
      });
    }
  }, [storeConnection?.last_sync_job?.status, isCancelling]);

  // Refetch source connection when sync fails to get latest error details
  useEffect(() => {
    const syncStatus = storeConnection?.last_sync_job?.status;
    const error = storeConnection?.last_sync_job?.error;
    if (syncStatus === 'failed' || error) {
      // Refetch to get the last_sync_job.error from backend
      fetchSourceConnection();
    }
  }, [storeConnection?.last_sync_job?.status, storeConnection?.last_sync_job?.error, fetchSourceConnection]);

  const handleRunSync = async () => {
    try {
      setIsRunningSync(true);
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
        // Clear isRunningSync once the sync has actually started
        setIsRunningSync(false);
      } else {
        throw new Error("Failed to start sync");
      }
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to start sync",
        variant: "destructive"
      });
      setIsRunningSync(false);
    }
  };

  const handleCancelSync = async () => {
    // Use job id from last_sync_job
    const jobId = storeConnection?.last_sync_job?.id || sourceConnection?.last_sync_job?.id;

    if (!jobId) {
      toast({
        title: "Error",
        description: "No active sync job to cancel",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsCancelling(true);
      console.log(`Cancelling sync job ${jobId} for connection ${sourceConnectionId}`);
      const response = await apiClient.post(`/source-connections/${sourceConnectionId}/jobs/${jobId}/cancel`);

      if (response.ok) {
        toast({
          title: "Cancellation Requested",
          description: "The sync is being cancelled. This may take a moment to complete.",
        });
        // Don't clear isCancelling here - it will be cleared when we detect the status change
      } else {
        const errorText = await response.text();
        throw new Error(errorText || "Failed to cancel sync job");
      }
    } catch (error) {
      console.error("Error cancelling sync:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to cancel sync job",
        variant: "destructive"
      });
      setIsCancelling(false);
    }
  };

  const handleConnectionUpdate = (updatedConnection: SourceConnection) => {
    setSourceConnection(updatedConnection);
    // Re-fetch to ensure everything is in sync
    fetchSourceConnection();
  };

  if (isInitializing && !connectionState) {
    return (
      <div className="w-full h-48 flex flex-col items-center justify-center space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className={cn(DESIGN_SYSTEM.typography.sizes.body, "text-muted-foreground")}>Loading entity state...</p>
      </div>
    );
  }

  // Sync states - use real-time updates from store if available, otherwise use source connection data
  const currentSyncJob = storeConnection?.last_sync_job || sourceConnection?.last_sync_job;
  const isRunning = currentSyncJob?.status === 'in_progress';
  const isPending = currentSyncJob?.status === 'pending' || currentSyncJob?.status === 'created';
  const isSyncing = isRunning || isPending;

  // Get sync status display
  const getSyncStatusDisplay = () => {
    if (sourceConnection?.status === 'not_yet_authorized' || !sourceConnection?.auth?.authenticated) {
      return { text: 'Not Authenticated', color: 'bg-cyan-500', icon: null };
    }
    if (currentSyncJob?.status === 'failed') return { text: 'Failed', color: 'bg-red-500', icon: null };
    if (currentSyncJob?.status === 'completed') return { text: 'Completed', color: 'bg-green-500', icon: null };
    if (isRunning) return { text: 'Syncing', color: 'bg-blue-500 animate-pulse', icon: 'loader' };
    if (isPending) return { text: 'Pending', color: 'bg-yellow-500 animate-pulse', icon: 'loader' };
    return { text: 'Ready', color: 'bg-gray-400', icon: null };
  };

  const syncStatus = getSyncStatusDisplay();
  const isNotAuthorized = sourceConnection?.status === 'not_yet_authorized' || !sourceConnection?.auth?.authenticated;

  return (
    <div className={cn("space-y-4", DESIGN_SYSTEM.typography.sizes.body)}>
      {/* Show authorization UI if not authorized */}
      {isNotAuthorized && sourceConnection && (
        <SourceAuthenticationView
          sourceName={sourceConnection.name}
          authenticationUrl={sourceConnection.auth?.auth_url}
          onRefreshUrl={handleRefreshAuthUrl}
          isRefreshing={isRefreshingAuth}
          showBorder={true}
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
            "h-8 px-3 py-1.5 rounded-md shadow-sm flex items-center gap-2 min-w-[90px]",
            // Highlight when sync is running
            (isRunning || isPending)
              ? isDark
                ? "bg-blue-900/30 border border-blue-700/50"
                : "bg-blue-50 border border-blue-200"
              : isDark
                ? "bg-gray-900 border border-border"
                : "bg-white border border-border"
          )}>
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">STATUS</span>
            <div className="flex items-center gap-1">
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
          <div className={cn("h-8 px-3 py-1.5 border border-border rounded-md shadow-sm flex items-center gap-2 min-w-[100px]", isDark ? "bg-gray-900" : "bg-white")}>
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">SCHEDULE</span>
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3 text-muted-foreground" />
              <span className="text-xs font-medium text-foreground">
                {sourceConnection?.schedule?.cron_expression ?
                  (nextRunTime ? `In ${nextRunTime}` : 'Scheduled') :
                  'Manual'}
              </span>
            </div>
          </div>

          {/* Last Sync Card - Only show when not actively syncing */}
          {!(isRunning || isPending) && (
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className={cn(
                    "h-8 px-3 py-1.5 rounded-md shadow-sm flex items-center gap-2 min-w-[100px] cursor-help",
                    isDark ? "bg-gray-900 border border-border" : "bg-white border border-border"
                  )}>
                    <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">LAST SYNC</span>
                    <div className="flex items-center gap-1">
                      <History className="h-3 w-3 text-muted-foreground" />
                      <span className="text-xs font-medium text-foreground">
                        {lastRanDisplay}
                      </span>
                    </div>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">
                    {formatExactTime(sourceConnection?.last_sync_job?.started_at)}
                  </p>
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
                  onClick={isSyncing ? handleCancelSync : handleRunSync}
                  disabled={isRunningSync || isCancelling || isNotAuthorized}
                  className={cn(
                    "h-8 w-8 rounded-md border shadow-sm flex items-center justify-center transition-all duration-200",
                    isNotAuthorized
                      ? "opacity-50 cursor-not-allowed bg-muted border-border"
                      : isSyncing
                        ? isCancelling
                          ? isDark
                            ? "bg-orange-900/30 border-orange-700 hover:bg-orange-900/50 cursor-not-allowed"
                            : "bg-orange-50 border-orange-200 hover:bg-orange-100 cursor-not-allowed"
                          : isDark
                            ? "bg-red-900/30 border-red-700 hover:bg-red-900/50 cursor-pointer"
                            : "bg-red-50 border-red-200 hover:bg-red-100 cursor-pointer"
                        : isRunningSync
                          ? "bg-muted border-border cursor-not-allowed"
                          : isDark
                            ? "bg-gray-900 border-border hover:bg-muted cursor-pointer"
                            : "bg-white border-border hover:bg-muted cursor-pointer"
                  )}
                  title={isSyncing ? (isCancelling ? "Cancelling sync..." : "Cancel sync") : (isRunningSync ? "Starting sync..." : "Refresh data")}
                >
                  {isSyncing ? (
                    isCancelling ? (
                      <Loader2 className="h-3 w-3 animate-spin text-orange-500" />
                    ) : (
                      <Square className="h-3 w-3 text-red-500" />
                    )
                  ) : (
                    <RefreshCw className={cn(
                      "h-3 w-3 text-muted-foreground",
                      isRunningSync && "animate-spin"
                    )} />
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <p className="text-xs">
                  {isNotAuthorized
                    ? "Authentication required before syncing"
                    : isSyncing
                      ? isCancelling
                        ? "Cancelling sync..."
                        : "Cancel sync"
                      : isRunningSync
                        ? "Starting sync..."
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
          onUpdate={handleConnectionUpdate}
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
          error={currentSyncJob?.error || sourceConnection?.last_sync_job?.error || "The last sync failed. Check the logs for more details."}
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
