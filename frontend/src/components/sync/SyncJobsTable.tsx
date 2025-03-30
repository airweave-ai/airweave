import { useEffect, useState, useCallback } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { format } from "date-fns";
import { apiClient } from "@/lib/api";

interface SyncJob {
  id: string;
  sync_id: string;
  status: 'completed' | 'failed' | 'running' | 'pending';
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
}

interface SyncJobsTableProps {
  syncId: string;
  onTotalRunsChange: (total: number) => void;
  onJobSelect: (jobId: string) => void;
}

export const SyncJobsTable: React.FC<SyncJobsTableProps> = ({
  syncId,
  onTotalRunsChange,
  onJobSelect
}) => {
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const handleRowClick = useCallback((jobId: string) => {
    onJobSelect(jobId);
  }, [onJobSelect]);

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const response = await apiClient.get(`/sync/${syncId}/jobs`);
        const jobsData: SyncJob[] = await response.json();
        setJobs(jobsData);
        onTotalRunsChange?.(jobsData.length);
      } catch (error) {
        console.error("Error fetching sync jobs:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchJobs();
  }, [syncId, onTotalRunsChange]);

  if (isLoading) {
    return <div className="p-6">Loading jobs...</div>;
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-semibold">Sync History</h2>
          <p className="text-muted-foreground mt-1">
            Overview of sync jobs and their status
          </p>
        </div>
      </div>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="font-semibold text-foreground">Created At</TableHead>
            <TableHead className="font-semibold text-foreground">Completed At</TableHead>
            <TableHead className="font-semibold text-foreground">Status</TableHead>
            <TableHead className="font-semibold text-foreground">Error</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.map((job) => (
            <TableRow
              key={job.id}
              onClick={() => handleRowClick(job.id)}
              className="cursor-pointer hover:bg-muted/50"
            >
              <TableCell>
                {format(new Date(job.created_at), "MMM d, yyyy HH:mm")}
              </TableCell>
              <TableCell>
                {job.completed_at
                  ? format(new Date(job.completed_at), "MMM d, yyyy HH:mm")
                  : '-'
                }
              </TableCell>
              <TableCell>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${job.status === "completed"
                      ? "bg-green-100 text-green-800"
                      : job.status === "failed"
                        ? "bg-red-100 text-red-800"
                        : job.status === "running"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-yellow-100 text-yellow-800"
                    }`}
                >
                  {job.status}
                </span>
              </TableCell>
              <TableCell className="max-w-md truncate">
                {job.error_message || '-'}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};