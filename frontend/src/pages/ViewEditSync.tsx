import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { format } from "date-fns";
import {
  ArrowLeft,
  Calendar,
  Clock,
  Database,
  Edit2,
  Pencil,
  Info,
  Zap,
  Play,
  ExternalLink,
  Eye,
  Copy,
  Activity,
  Box,
  Heart,
  RefreshCw,
  Check,
  X,
  Trash
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SyncJobsTable } from "@/components/sync/SyncJobsTable";
import { SyncDagEditor } from "@/components/sync/SyncDagEditor";
import { DeleteSyncDialog } from "@/components/sync/DeleteSyncDialog";
import { toast } from "@/hooks/use-toast";
import { apiClient } from "@/lib/api";
import { Sync, SyncDetailsData } from "@/components/sync/types";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { SyncProgress } from "@/components/sync/SyncProgress";
import { Badge } from "@/components/ui/badge";
import { getAppIconUrl } from "@/lib/utils/icons";
import { getDestinationIconUrl } from "@/lib/utils/icons";
import { Input } from "@/components/ui/input";
import { SyncSchedule, SyncScheduleConfig } from "@/components/sync/SyncSchedule";
import "./sync-progress.css"; // Import custom CSS for animations
import { useSyncSubscription } from "@/hooks/useSyncSubscription";

interface SyncDetails {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  modified_at: string;
  cron_schedule: string | null;
  created_by_email: string;
  organization_id: string;
  source_connection_id: string;
  destination_connection_id: string;
  modified_by_email: string;
}

// Add interfaces for API responses
interface ConnectionResponse {
  integration_type: string;
  name: string;
  short_name: string;
}

interface DestinationResponse {
  integration_type: string;
  name: string;
  short_name: string;
}

interface SyncJob {
  id: string;
  sync_id: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';  // from SyncJobStatus enum
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  entities_inserted: number;
  entities_updated: number;
  entities_deleted: number;
  entities_kept: number;
  entities_skipped: number;
  error: string | null;
  created_at: string;
  modified_at: string;
  organization_id: string;
  created_by_email: string;
  modified_by_email: string;
}

const ViewEditSync = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [syncDetails, setSyncDetails] = useState<SyncDetailsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [destinationData, setDestinationData] = useState<any>(null);
  const [totalRuns, setTotalRuns] = useState<number>(0);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<SyncJob | null>(null);
  const [isRunningSync, setIsRunningSync] = useState(false);
  const [totalRuntime, setTotalRuntime] = useState<number | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Name editing state
  const [isEditingName, setIsEditingName] = useState(false);
  const [syncName, setSyncName] = useState("");
  const nameInputRef = useRef<HTMLInputElement>(null);

  // Schedule editing state
  const [showScheduleDialog, setShowScheduleDialog] = useState(false);
  const [scheduleConfig, setScheduleConfig] = useState<SyncScheduleConfig>({
    type: "one-time",
    frequency: "custom"
  });

  const liveUpdates = useSyncSubscription(lastSync?.id);
  const latestUpdate = liveUpdates.length > 0 ? liveUpdates[liveUpdates.length - 1] : null;

  // Derive status from the update flags
  let liveStatus = lastSync?.status;
  if (latestUpdate) {
    if (latestUpdate.is_complete === true) {
      liveStatus = "completed";
    } else if (latestUpdate.is_failed === true) {
      liveStatus = "failed";
    } else {
      // If we have updates but neither complete nor failed, it must be in progress
      liveStatus = "in_progress";
    }
  }

  const status = (liveStatus || lastSync?.status || "").toLowerCase();

  const fetchLastSyncJob = async () => {
    try {
      if (!id) return;

      // Fetch all sync jobs for this sync
      const jobsResponse = await apiClient.get(`/sync/${id}/jobs`);
      if (!jobsResponse.ok) throw new Error("Failed to fetch sync jobs");

      const syncJobs: SyncJob[] = await jobsResponse.json();

      // Sort jobs by created_at date (newest first)
      const sortedJobs = syncJobs.sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );

      // Set the most recent job as the last sync
      if (sortedJobs.length > 0) {
        setLastSync(sortedJobs[0]);

        // Calculate total runtime across all completed jobs
        let totalTime = 0;
        syncJobs.forEach(job => {
          // Use completed_at or failed_at as the end time
          const endTime = job.completed_at || job.failed_at;
          if (job.started_at && endTime) {
            totalTime += new Date(endTime).getTime() - new Date(job.started_at).getTime();
          }
        });
        setTotalRuntime(totalTime);
      }
    } catch (error) {
      console.error("Error fetching last sync job:", error);
    }
  };

  const refreshData = async () => {
    setIsRefreshing(true);
    try {
      await fetchSyncDetails();
      await fetchLastSyncJob();
    } finally {
      setIsRefreshing(false);
    }
  };

  // Add a function to fetch only the sync details
  const fetchSyncDetails = async () => {
    try {
      if (!id) return;

      // Fetch sync details
      const syncResponse = await apiClient.get(`/sync/${id}`);

      if (!syncResponse.ok) {
        throw new Error("Failed to fetch sync details");
      }

      const syncData: SyncDetails = await syncResponse.json();

      // Fetch source connection
      const sourceConnection = await apiClient.get(`/connections/detail/${syncData.source_connection_id}`);
      const sourceData: ConnectionResponse = await sourceConnection.json();

      // Fetch destination connection
      let destinationData: DestinationResponse;
      if (syncData.destination_connection_id) {
        const destConnection = await apiClient.get(`/connections/detail/${syncData.destination_connection_id}`);
        const destConnectionData = await destConnection.json();
        const destination = await apiClient.get(`/destinations/detail/${destConnectionData.short_name}`);
        destinationData = await destination.json();
      } else {
        // native qdrant
        const destination = await apiClient.get(`/destinations/detail/qdrant_native`);
        destinationData = await destination.json();
      }

      const transformToSyncDetailsData = (
        syncData: SyncDetails,
        source: ConnectionResponse,
        destination: DestinationResponse
      ): SyncDetailsData => ({
        ...syncData,
        createdAt: syncData.created_at,
        modifiedAt: syncData.modified_at,
        cronSchedule: syncData.cron_schedule,
        sourceConnectionId: syncData.source_connection_id,
        destinationConnectionId: syncData.destination_connection_id,
        organizationId: syncData.organization_id,
        createdByEmail: syncData.created_by_email,
        modifiedByEmail: syncData.modified_by_email,
        status: "active", // You might want to determine this based on actual sync status
        totalRuns: totalRuns,
        uiMetadata: {
          source: {
            type: source.integration_type?.toLowerCase() ?? 'Source',
            name: source.name ?? 'Unknown Source',
            shortName: source.short_name ?? 'unknown'
          },
          destination: {
            type: destination.integration_type?.toLowerCase() ?? 'Destination',
            name: destination.name ?? 'Native Airweave',
            shortName: destination.short_name ?? (destinationData.short_name === 'qdrant_native' ? 'Native' : 'unknown')
          },
          userId: syncData.created_by_email,
          organizationId: syncData.organization_id,
          userEmail: syncData.created_by_email
        }
      });

      const syncDetailsData = transformToSyncDetailsData(syncData, sourceData, destinationData);
      setSyncDetails(syncDetailsData);

      // Update schedule config based on new data
      setScheduleConfig({
        type: syncData.cron_schedule ? "scheduled" : "one-time",
        frequency: "custom",
        cronExpression: syncData.cron_schedule || undefined
      });

    } catch (error) {
      console.error("Error fetching sync details:", error);
      toast({
        title: "Error",
        description: "Failed to refresh sync details",
        variant: "destructive"
      });
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        await fetchSyncDetails();
        setIsLoading(false);
        // Fetch last sync job after basic data is loaded
        await fetchLastSyncJob();
      } catch (error) {
        console.error("Error fetching sync data:", error);
        toast({
          title: "Error",
          description: "Failed to load sync details",
          variant: "destructive"
        });
        setIsLoading(false);
      }
    };

    if (id) {
      fetchData();
    }
  }, [id]);

  useEffect(() => {
    // Set the initial schedule config when syncDetails is loaded
    if (syncDetails) {
      setScheduleConfig({
        type: syncDetails.cronSchedule ? "scheduled" : "one-time",
        frequency: "custom",
        cronExpression: syncDetails.cronSchedule || undefined
      });
      if (!isEditingName) {
        setSyncName(syncDetails.name);
      }
    }
  }, [syncDetails, isEditingName]);

  // Add this effect to refresh the lastSync data when a sync completes
  useEffect(() => {
    // When a live sync transitions from running to complete/failed, refresh the job data
    if (latestUpdate && (latestUpdate.is_complete || latestUpdate.is_failed)) {
      // Fetch the latest job data to get accurate stats
      fetchLastSyncJob();
    }
  }, [latestUpdate?.is_complete, latestUpdate?.is_failed]);

  const handleDelete = async () => {
    try {
      await apiClient.delete(`/sync/${id}`);
      toast({
        title: "Success",
        description: "Synchronization deleted successfully"
      });
      navigate("/sync");
    } catch (error) {
      console.error("Error deleting sync:", error);
      toast({
        title: "Error",
        description: "Failed to delete synchronization",
        variant: "destructive"
      });
    }
  };

  const handleJobSelect = (jobId: string) => {
    setSelectedJobId(jobId);
  };

  const handleEdit = () => {
    navigate(`/sync/${id}/edit`);
  };

  const handleRunSync = async () => {
    try {
      setIsRunningSync(true);
      const response = await apiClient.post(`/sync/${id}/run`);

      if (!response.ok) {
        throw new Error("Failed to start sync job");
      }

      const newJob = await response.json();

      toast({
        title: "Success",
        description: "Sync job started successfully"
      });

      // Update the last sync job immediately
      setLastSync(newJob);
    } catch (error) {
      console.error("Error running sync:", error);
      toast({
        title: "Error",
        description: "Failed to start sync job",
        variant: "destructive"
      });
    } finally {
      setIsRunningSync(false);
    }
  };

  const viewLastSyncJob = () => {
    if (lastSync) {
      // Navigate to the job details page
      navigate(`/sync/${id}/job/${lastSync.id}`);
    }
  };

  // Format milliseconds to human-readable time (days, hours, minutes, seconds)
  const formatTotalRuntime = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) {
      return `${days}d ${hours % 24}h`;
    } else if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  };

  if (isLoading) {
    return <div>Loading...</div>;
  }

  const getNextRunText = () => {
    if (!syncDetails?.cronSchedule) {
      return "Manual trigger";
    }
    // For this example, we're not calculating the actual next run time
    // A proper implementation would parse the cron schedule and calculate the next run
    return `Scheduled (${syncDetails.cronSchedule})`;
  };

  const startEditingName = () => {
    setIsEditingName(true);
    // Set input's initial value to current name only once when starting to edit
    if (nameInputRef.current) {
      nameInputRef.current.value = syncDetails?.name || "";
    }
    setTimeout(() => nameInputRef.current?.focus(), 0);
  };

  const handleSaveNameChange = async () => {
    // Get value directly from input ref instead of state to avoid re-renders during typing
    const newName = nameInputRef.current?.value || "";

    if (!newName.trim() || newName === syncDetails?.name) {
      setIsEditingName(false);
      return;
    }

    try {
      const response = await apiClient.patch(`/sync/${id}`, { name: newName });
      if (!response.ok) throw new Error("Failed to update sync name");

      // Update local state only after successful API call
      setSyncDetails(prev => prev ? { ...prev, name: newName } : null);
      setIsEditingName(false);

      toast({
        title: "Success",
        description: "Sync name updated successfully"
      });
    } catch (error) {
      console.error("Error updating sync name:", error);
      toast({
        title: "Error",
        description: "Failed to update sync name",
        variant: "destructive"
      });
      setIsEditingName(false);
    }
  };

  // Modify the refreshScheduleData function to remove references to setScheduleText
  const refreshScheduleData = async () => {
    if (!id) return;

    try {
      console.log("Starting schedule refresh");
      // Show loading indicator
      setIsRefreshing(true);

      // Make a targeted API call to get just the sync details
      const response = await apiClient.get(`/sync/${id}`);
      if (!response.ok) throw new Error("Failed to refresh sync data");

      const syncData = await response.json();
      console.log("Got sync data:", syncData);

      // Update the state with the new schedule information
      setSyncDetails(prevDetails => {
        if (!prevDetails) return null;
        console.log("Updating sync details", prevDetails, "with cron_schedule:", syncData.cron_schedule);
        const updated = {
          ...prevDetails,
          cronSchedule: syncData.cron_schedule,
          modifiedAt: syncData.modified_at
        };
        console.log("Updated details:", updated);
        return updated;
      });

      // Update the config state as well
      setScheduleConfig({
        type: syncData.cron_schedule ? "scheduled" : "one-time",
        frequency: "custom",
        cronExpression: syncData.cron_schedule || undefined
      });

      toast({
        title: "Success",
        description: "Schedule updated successfully"
      });
    } catch (error) {
      console.error("Error refreshing schedule data:", error);
      toast({
        title: "Error",
        description: "Failed to refresh schedule data",
        variant: "destructive"
      });
    } finally {
      setIsRefreshing(false);
      console.log("Schedule refresh complete");
    }
  };

  return (
    <div className="container mx-auto pb-8 space-y-6 max-w-screen-2xl">
      {/* Header with Title and Status Badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/sync")}
            className="text-muted-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            {isEditingName ? (
              <div className="flex items-center gap-2">
                <Input
                  ref={nameInputRef}
                  // Use uncontrolled input to prevent re-renders during typing
                  defaultValue={syncDetails?.name || ""}
                  className="text-xl font-bold h-9 min-w-[300px]"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleSaveNameChange();
                    }
                    if (e.key === 'Escape') {
                      setIsEditingName(false);
                    }
                  }}
                  onBlur={handleSaveNameChange}
                />
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight">{syncDetails?.name}</h1>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={startEditingName}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Badge className="rounded-full font-semibold">{syncDetails?.status?.toUpperCase()}</Badge>
              </div>
            )}
            <p className="text-muted-foreground text-sm mt-1">
              {syncDetails?.id}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={refreshData}
            disabled={isRefreshing}
            className="gap-1"
          >
            <RefreshCw className="h-4 w-4" />
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
          <Button
            variant="default"
            onClick={handleRunSync}
            disabled={isRunningSync || lastSync?.status === 'in_progress' || lastSync?.status === 'pending'}
          >
            <Play className="mr-2 h-4 w-4" />
            {isRunningSync ? 'Starting...' : 'Run Sync'}
          </Button>
          <Button
            variant="outline"
            onClick={() => setShowDeleteDialog(true)}
            className="text-destructive hover:bg-destructive/10"
          >
            <Trash className="mr-2 h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      <div className="space-y-6">
        {/* First row: Sync Overview and Sync Status cards side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sync Overview - 3/4 width */}
          <div className="lg:col-span-3">
            <Card className="p-5 border rounded-lg bg-card h-full">
              <div className="space-y-6">
                <h3 className="text-lg font-medium">Sync Overview</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Source and Destination */}
                  <div className="space-y-6">
                    {/* Source */}
                    <div className="flex gap-4">
                      <div className="flex-shrink-0 h-10 w-10 bg-primary/10 rounded-full flex items-center justify-center">
                        <Box className="h-5 w-5 text-primary" />
                      </div>
                      <div className="space-y-1.5">
                        <h4 className="font-medium">Source</h4>
                        <div className="flex items-center gap-2">
                          {syncDetails?.uiMetadata.source.shortName && (
                            <img
                              src={getAppIconUrl(syncDetails?.uiMetadata.source.shortName)}
                              alt={syncDetails?.uiMetadata.source.name}
                              className="h-5 w-5 flex-shrink-0"
                            />
                          )}
                          <span>{syncDetails?.uiMetadata.source.name}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <button
                            className="text-xs text-muted-foreground hover:text-primary flex items-center"
                            onClick={() => {
                              navigator.clipboard.writeText(syncDetails?.sourceConnectionId || '');
                              toast({ title: "Copied connection ID" });
                            }}
                          >
                            <span>{syncDetails?.sourceConnectionId}</span>
                            <Copy className="h-3 w-3 ml-0.5" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Destination */}
                    <div className="flex gap-4">
                      <div className="flex-shrink-0 h-10 w-10 bg-primary/10 rounded-full flex items-center justify-center">
                        <Database className="h-5 w-5 text-primary" />
                      </div>
                      <div className="space-y-1.5">
                        <h4 className="font-medium">Destination</h4>
                        <div className="flex items-center gap-2">
                          {syncDetails?.uiMetadata.destination.shortName && (
                            syncDetails?.uiMetadata.destination.shortName === "Native" ? (
                              <div className="h-5 w-5 flex items-center justify-center flex-shrink-0">
                                <Database className="h-4 w-4" />
                              </div>
                            ) : (
                              <img
                                src={getDestinationIconUrl(syncDetails?.uiMetadata.destination.shortName)}
                                alt={syncDetails?.uiMetadata.destination.name}
                                className="h-5 w-5 flex-shrink-0"
                                onError={(e) => {
                                  e.currentTarget.onerror = null;
                                  e.currentTarget.style.display = 'none';
                                  const parent = e.currentTarget.parentElement;
                                  if (parent) {
                                    const fallback = document.createElement('div');
                                    fallback.className = 'h-5 w-5 flex items-center justify-center flex-shrink-0';
                                    fallback.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16"><path fill="none" d="M0 0h24v24H0z"/><path d="M3 12h3v9H3v-9zm15-9H6v9h12V3z" fill="currentColor"/></svg>';
                                    parent.prepend(fallback);
                                  }
                                }}
                              />
                            )
                          )}
                          <span>{syncDetails?.uiMetadata.destination.name}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {syncDetails?.destinationConnectionId && (
                            <button
                              className="text-xs text-muted-foreground hover:text-primary flex items-center"
                              onClick={() => {
                                navigator.clipboard.writeText(syncDetails?.destinationConnectionId || '');
                                toast({ title: "Copied connection ID" });
                              }}
                            >
                              <span>{syncDetails?.destinationConnectionId}</span>
                              <Copy className="h-3 w-3 ml-0.5" />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Created Info and Sync Jobs */}
                  <div className="space-y-6">
                    {/* Created Info */}
                    <div className="flex gap-4">
                      <div className="flex-shrink-0 h-10 w-10 bg-primary/10 rounded-full flex items-center justify-center">
                        <Calendar className="h-5 w-5 text-primary" />
                      </div>
                      <div className="space-y-1.5">
                        <h4 className="font-medium">Created</h4>
                        <div className="space-y-1">
                          <div className="text-sm">
                            <span className="text-muted-foreground mr-2">Date:</span>
                            <span>{format(new Date(syncDetails?.createdAt || Date.now()), 'MMM dd, yyyy')}</span>
                          </div>
                          <div className="text-sm">
                            <span className="text-muted-foreground mr-2">By:</span>
                            <span>{syncDetails?.createdByEmail}</span>
                          </div>
                          <div className="text-sm">
                            <span className="text-muted-foreground mr-2">Last Updated:</span>
                            <span>{format(new Date(syncDetails?.modifiedAt || Date.now()), 'MMM dd, yyyy')}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Sync Jobs */}
                    <div className="flex gap-4">
                      <div className="flex-shrink-0 h-10 w-10 bg-primary/10 rounded-full flex items-center justify-center">
                        <Activity className="h-5 w-5 text-primary" />
                      </div>
                      <div className="space-y-1.5">
                        <h4 className="font-medium">Sync Jobs</h4>
                        <div className="flex items-center">
                          <span className="text-lg font-medium">{totalRuns}</span>
                          <span className="text-xs text-muted-foreground ml-1.5">total runs</span>
                          {totalRuntime !== null && (
                            <div className="flex items-center ml-3 text-xs text-muted-foreground">
                              <Clock className="h-3 w-3 mr-0.5" />
                              <span>{formatTotalRuntime(totalRuntime)} runtime</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {syncDetails?.description && (
                  <div className="pt-4 mt-2 border-t">
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 h-6 w-6 flex items-center justify-center">
                        <Info className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div>
                        <h4 className="text-sm font-medium">Description</h4>
                        <p className="text-sm mt-1 text-muted-foreground">{syncDetails.description}</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Sync Status - 1/4 width */}
          <div className="lg:col-span-1">
            <Card className="p-5 border rounded-lg bg-card h-full">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium">Sync Status</h3>
                {lastSync && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={viewLastSyncJob}
                    className="hover:bg-muted"
                  >
                    <Eye className="h-4 w-4 mr-1" />
                    Details
                  </Button>
                )}
              </div>

              {/* Schedule info */}
              <div className="mb-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex-shrink-0 h-9 w-9 bg-blue-500/10 rounded-full flex items-center justify-center">
                      <Clock className="w-4 h-4 text-blue-500" />
                    </div>
                    <div>
                      <h4 className="text-sm font-medium">Schedule</h4>
                      <p className="text-sm text-muted-foreground">{getNextRunText()}</p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0"
                    onClick={() => {
                      setScheduleConfig({
                        type: syncDetails?.cronSchedule ? "scheduled" : "one-time",
                        frequency: "custom",
                        cronExpression: syncDetails?.cronSchedule || undefined
                      });
                      setShowScheduleDialog(true);
                    }}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>

              {lastSync ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex-shrink-0 h-9 w-9 bg-amber-500/10 rounded-full flex items-center justify-center">
                      <Calendar className="w-4 h-4 text-amber-500" />
                    </div>
                    <div>
                      <h4 className="text-sm font-medium">Last Run</h4>
                      <p className="text-sm">
                        {format(new Date(lastSync.created_at), 'MMM dd, yyyy h:mm a')}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 mb-2">
                    <div className={`flex-shrink-0 h-9 w-9 rounded-full flex items-center justify-center
                      ${status === "completed" ? "bg-green-500/10" :
                        status === "failed" ? "bg-red-500/10" :
                          "bg-blue-500/10"}`}>
                      <Activity className={`w-4 h-4
                        ${status === "completed" ? "text-green-500" :
                          status === "failed" ? "text-red-500" :
                            "text-blue-500"}`} />
                    </div>
                    <div>
                      <h4 className="text-sm font-medium">Status</h4>
                      <p className="capitalize text-sm">
                        {status === "in_progress" ? "running" : status}
                        {(status === "in_progress" || status === "pending") && <span className="ml-1 animate-pulse">...</span>}
                      </p>
                    </div>
                  </div>

                  {lastSync.started_at && (
                    <div className="flex items-center gap-3 mb-2">
                      <div className="flex-shrink-0 h-9 w-9 bg-purple-500/10 rounded-full flex items-center justify-center">
                        <Clock className="w-4 h-4 text-purple-500" />
                      </div>
                      <div>
                        <h4 className="text-sm font-medium">Duration</h4>
                        <p className="text-sm">
                          {(lastSync.completed_at || lastSync.failed_at) ?
                            `${Math.round((new Date(lastSync.completed_at || lastSync.failed_at || '').getTime() - new Date(lastSync.started_at).getTime()) / 1000)} seconds` :
                            "-"}
                        </p>
                      </div>
                    </div>
                  )}

                  {lastSync.error && (
                    <div className="mt-4 p-3 bg-red-100 text-red-800 rounded-md text-sm">
                      <p className="font-semibold">Error:</p>
                      <p className="text-xs mt-1">{lastSync.error}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <p className="text-muted-foreground mb-3">No sync jobs have been run yet.</p>
                  <Button
                    onClick={handleRunSync}
                    variant="outline"
                    className="mt-2"
                    disabled={isRunningSync}
                  >
                    Run First Sync
                  </Button>
                </div>
              )}
            </Card>
          </div>
        </div>

        {/* Live Sync Progress or Final Card */}
        {lastSync && (
          <div className="w-full flex justify-center my-8">
            <SyncProgress
              syncId={id || null}
              syncJobId={lastSync.id}
              lastSync={lastSync}
              isLive={status === "in_progress" || status === "pending"}
            />
          </div>
        )}

        {/* Sync DAG (full width) */}
        <Card className="border rounded-lg bg-card">
          <div className="p-5">
            <SyncDagEditor syncId={id || ''} />
          </div>
        </Card>

        {/* Sync Jobs Table */}
        <Card className="border rounded-lg bg-card">
          <SyncJobsTable
            syncId={id || ''}
            onTotalRunsChange={(total) => setTotalRuns(total)}
            onJobSelect={handleJobSelect}
          />
        </Card>
      </div>

      {/* Schedule Edit Dialog */}
      <Dialog
        open={showScheduleDialog}
        onOpenChange={(open) => {
          const wasOpen = showScheduleDialog;
          setShowScheduleDialog(open);

          // When dialog closes, force a refresh
          if (wasOpen && !open) {
            console.log("Dialog closing, refreshing data");
            // Give time for the SyncSchedule component to complete any pending operations
            setTimeout(() => {
              refreshScheduleData();
            }, 500);
          }
        }}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Edit Sync Schedule</DialogTitle>
          </DialogHeader>

          <div className="py-4">
            <SyncSchedule
              value={scheduleConfig}
              onChange={(newConfig) => {
                console.log("Schedule config changed:", newConfig);
                setScheduleConfig(newConfig);
              }}
              syncId={id}
            />
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                console.log("Done button clicked");
                setShowScheduleDialog(false);
                // Simple and direct approach - reload the page when the dialog closes
                setTimeout(() => window.location.reload(), 300);
              }}
            >
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Job Details Dialog */}
      <Dialog
        open={!!selectedJobId}
        onOpenChange={(open) => !open && setSelectedJobId(null)}
      >
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Sync Progress</DialogTitle>
          </DialogHeader>
          <SyncProgress
            syncId={id || null}
            syncJobId={selectedJobId}
          />
        </DialogContent>
      </Dialog>

      <DeleteSyncDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        onConfirm={handleDelete}
      />
    </div>
  );
};

export default ViewEditSync;
