import { useState, useEffect } from "react";
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
  RefreshCw
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SyncJobsTable } from "@/components/sync/SyncJobsTable";
import { SyncDagEditor } from "@/components/sync/SyncDagEditor";
import { DeleteSyncDialog } from "@/components/sync/DeleteSyncDialog";
import { toast } from "@/hooks/use-toast";
import { apiClient } from "@/lib/api";
import { Sync, SyncDetailsData } from "@/components/sync/types";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { SyncProgress } from "@/components/sync/SyncProgress";
import { Badge } from "@/components/ui/badge";
import { getAppIconUrl } from "@/lib/utils/icons";
import { getDestinationIconUrl } from "@/lib/utils/icons";
import "./sync-progress.css"; // Import custom CSS for animations

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
  status: "success" | "failed" | "running" | "pending";
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  error_message: string | null;
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
  const [userInfo, setUserInfo] = useState<{
    userId: string;
    organizationId: string;
    userEmail: string;
  } | null>(null);

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
          if (job.started_at && job.ended_at) {
            totalTime += new Date(job.ended_at).getTime() - new Date(job.started_at).getTime();
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
      await fetchLastSyncJob();
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);

        // Fetch sync details
        const syncResponse = await apiClient.get(`/sync/${id}`);
        const syncData: SyncDetails = await syncResponse.json();

        // Extract user info from sync data
        setUserInfo({
          userId: syncData.created_by_email,
          organizationId: syncData.organization_id,
          userEmail: syncData.created_by_email
        });

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
          // native weaviate
          const destination = await apiClient.get(`/destinations/detail/qdrant`);
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
              name: 'Native Qdrant',
              shortName: destination.short_name ?? ( destinationData.short_name === 'qdrant' ? 'Native' : 'unknown')
            },
            userId: syncData.created_by_email,
            organizationId: syncData.organization_id,
            userEmail: syncData.created_by_email
          }
        });

        const syncDetailsData = transformToSyncDetailsData(syncData, sourceData, destinationData);
        setSyncDetails(syncDetailsData);

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

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'success': return { bg: 'bg-muted', text: 'text-foreground' };
      case 'failed': return { bg: 'bg-muted', text: 'text-foreground' };
      case 'running': return { bg: 'bg-muted', text: 'text-foreground' };
      case 'pending': return { bg: 'bg-muted', text: 'text-foreground' };
      default: return { bg: 'bg-muted', text: 'text-foreground' };
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
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">{syncDetails?.name}</h1>
              <Badge className="rounded-full font-semibold">{syncDetails?.status?.toUpperCase()}</Badge>
            </div>
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
            disabled={isRunningSync || lastSync?.status === 'running' || lastSync?.status === 'pending'}
          >
            <Play className="mr-2 h-4 w-4" />
            {isRunningSync ? 'Starting...' : 'Run Sync'}
          </Button>
          <Button variant="outline" onClick={handleEdit}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit
          </Button>
        </div>
      </div>

      <div className="space-y-6">
        {/* First row: Sync Overview and Last Sync cards side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sync Overview - 3/4 width */}
          <div className="lg:col-span-3">
            <Card className="p-5 border rounded-lg bg-card h-full">
              <div className="space-y-4">
                <h3 className="text-lg font-medium">Sync Overview</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
                  {/* Left Column */}
                  <div className="space-y-6">
                    {/* Source */}
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <div className="flex-shrink-0 h-5 w-5">
                          <Box className="h-full w-full" />
                        </div>
                        <span className="text-sm font-medium">Source</span>
                      </div>
                      <div className="ml-7">
                        <div className="flex items-center gap-2">
                          {syncDetails?.uiMetadata.source.shortName && (
                            <img
                              src={getAppIconUrl(syncDetails?.uiMetadata.source.shortName)}
                              alt={syncDetails?.uiMetadata.source.name}
                              className="h-5 w-5 flex-shrink-0"
                            />
                          )}
                          <p className="font-medium">{syncDetails?.uiMetadata.source.name}</p>
                        </div>
                        <div className="flex items-center gap-1.5 mt-1">
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
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <div className="flex-shrink-0 h-5 w-5">
                          <Database className="h-full w-full" />
                        </div>
                        <span className="text-sm font-medium">Destination</span>
                      </div>
                      <div className="ml-7">
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
                                  // Fallback if image fails to load
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
                          <p className="font-medium">{syncDetails?.uiMetadata.destination.name}</p>
                        </div>
                        <div className="flex items-center gap-1.5 mt-1">
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

                    {/* Schedule */}
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <div className="flex-shrink-0 h-5 w-5">
                          <Clock className="h-full w-full" />
                        </div>
                        <span className="text-sm font-medium">Schedule</span>
                      </div>
                      <div className="ml-7">
                        {syncDetails?.cronSchedule ? (
                          <p className="font-medium">{syncDetails.cronSchedule}</p>
                        ) : (
                          <p className="font-medium">Manual Trigger Only</p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right Column */}
                  <div className="space-y-6">
                    {/* Status */}
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <div className="flex-shrink-0 h-5 w-5 flex items-center justify-center">
                          <Activity className="h-4 w-4" />
                        </div>
                        <span className="text-sm font-medium">Status</span>
                      </div>
                      <div className="ml-7">
                        <div className="flex items-center gap-2">
                          <Badge className="rounded-full text-xs px-3 py-0.5">Active</Badge>
                          {lastSync && (
                            <span className="text-xs text-muted-foreground">
                              Last run {format(new Date(lastSync.created_at), 'MMM dd, yyyy')}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Created Info */}
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <div className="flex-shrink-0 h-5 w-5">
                          <Clock className="h-full w-full" />
                        </div>
                        <span className="text-sm font-medium">Created</span>
                      </div>
                      <div className="ml-7">
                        <div className="grid grid-cols-2 gap-y-1 text-sm">
                          <span className="text-muted-foreground">Date</span>
                          <span className="text-right">{format(new Date(syncDetails?.createdAt || Date.now()), 'MMM dd, yyyy')}</span>
                          <span className="text-muted-foreground">Last Updated</span>
                          <span className="text-right">{format(new Date(syncDetails?.modifiedAt || Date.now()), 'MMM dd, yyyy')}</span>
                          <span className="text-muted-foreground">By</span>
                          <span className="text-right">{syncDetails?.createdByEmail}</span>
                        </div>
                      </div>
                    </div>

                    {/* Sync Jobs */}
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <div className="flex-shrink-0 h-5 w-5">
                          <Database className="h-full w-full" />
                        </div>
                        <span className="text-sm font-medium">Sync Jobs</span>
                      </div>
                      <div className="ml-7">
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
                  <div className="pt-3 mt-3 border-t">
                    <div className="flex items-start gap-2">
                      <Info className="h-3.5 w-3.5 text-muted-foreground mt-0.5" />
                      <div>
                        <span className="text-muted-foreground text-xs font-medium">Description</span>
                        <p className="text-sm mt-1">{syncDetails.description}</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Last Sync info - 1/4 width */}
          <div className="lg:col-span-1">
            <Card className="p-5 border rounded-lg bg-card overflow-hidden relative group h-full flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium">Last Sync</h3>
                {lastSync && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={viewLastSyncJob}
                    className="hover:bg-muted"
                  >
                    <Eye className="h-4 w-4 mr-1" />
                    View
                  </Button>
                )}
              </div>

              {lastSync ? (
                <div className="space-y-4 flex-grow">
                  <div className="flex items-center">
                    <div className={`w-10 h-10 mr-3 rounded-full flex items-center justify-center`}>
                      <Clock className={`w-5 h-5 text-blue-500/80`} />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Time</p>
                      <p className="font-medium text-base">
                        {format(new Date(lastSync.created_at), 'h:mm a')}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center">
                    <div className="w-10 h-10 mr-3 bg-blue-500/10 rounded-full flex items-center justify-center">
                      <Calendar className="w-5 h-5 text-blue-500/80" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Date</p>
                      <p className="font-medium text-base">
                        {format(new Date(lastSync.created_at), 'MMM dd, yyyy')}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center">
                    <div className={`w-10 h-10 mr-3 ${getStatusColor(lastSync.status).bg} rounded-full flex items-center justify-center`}>
                      <Heart className={`w-5 h-5 text-red-500 ${getStatusColor(lastSync.status).text}`} />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Status</p>
                      <p className="font-medium text-base capitalize">
                        {lastSync.status}
                      </p>
                    </div>
                  </div>
                  {lastSync.started_at && lastSync.ended_at && (
                    <div className="flex items-center">
                      <div className="w-10 h-10 mr-3 bg-amber-500/10 rounded-full flex items-center justify-center">
                        <Clock className="w-5 h-5 text-amber-500/80" />
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Duration</p>
                        <p className="font-medium text-base">
                          {Math.round((new Date(lastSync.ended_at).getTime() - new Date(lastSync.started_at).getTime()) / 1000)} seconds
                        </p>
                      </div>
                    </div>
                  )}
                  {totalRuntime !== null && (
                    <div className="flex items-center">
                      <div className="w-10 h-10 mr-3 bg-purple-500/10 rounded-full flex items-center justify-center">
                        <Clock className="w-5 h-5 text-purple-500/80" />
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Total Runtime</p>
                        <p className="font-medium text-base">
                          {formatTotalRuntime(totalRuntime)}
                        </p>
                      </div>
                    </div>
                  )}
                  {lastSync.error_message && (
                    <div className="mt-3 p-2.5 bg-red-100 text-red-800 rounded-md text-sm">
                      <p className="font-semibold">Error:</p>
                      <p>{lastSync.error_message}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-6 text-muted-foreground flex-grow flex flex-col justify-center">
                  <p>No sync jobs have been run yet.</p>
                  <Button
                    onClick={handleRunSync}
                    variant="outline"
                    className="mt-3"
                    disabled={isRunningSync}
                  >
                    Run First Sync
                  </Button>
                </div>
              )}
            </Card>
          </div>
        </div>

        {/* Live Sync Progress View - Only shown when sync is running */}
        {lastSync && (lastSync.status === "running" || lastSync.status === "pending") && (
          <div className="rounded-lg overflow-hidden">
            <SyncProgress
              syncId={id || null}
              syncJobId={lastSync.id}
              isLive={true}
              startedAt={lastSync.started_at}
            />
          </div>
        )}

        {/* Second row: Sync DAG (full width) */}
          <Card className="border rounded-lg overflow-hidden px-3 py-2">
            <SyncDagEditor syncId={id || ''} />
          </Card>

        {/* Sync Jobs Table */}
        <div>
          <h3 className="text-lg font-medium mb-2">Sync Jobs</h3>
          <Card>
            <SyncJobsTable
              syncId={id || ''}
              onTotalRunsChange={(total) => setTotalRuns(total)}
              onJobSelect={handleJobSelect}
            />
          </Card>
        </div>
      </div>

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
