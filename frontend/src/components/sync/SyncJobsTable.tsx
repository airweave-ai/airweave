import { useEffect, useState } from "react";
import { format } from "date-fns";
import { apiClient } from "@/lib/api";
import { DataTable, Column } from "@/components/ui/data-table";

interface SyncJob {
  id: string;
  sync_id: string;
  status: 'completed' | 'failed' | 'running' | 'pending';
  created_at: string;
  completed_at: string | null;
  error: string | null;
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
  const [search, setSearch] = useState("");

  useEffect(() => {
    const fetchJobs = async () => {
      setIsLoading(true);
      try {
        const response = await apiClient.get(`/sync/${syncId}/jobs`);
        const data: SyncJob[] = await response.json();
        setJobs(data);
        onTotalRunsChange?.(data.length);
      } catch (error) {
        console.error("Error fetching sync jobs:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchJobs();
  }, [syncId, onTotalRunsChange]);

  // Filter by search term
  const filteredJobs = jobs.filter(job =>
    job.status.toLowerCase().includes(search.toLowerCase())
  );

  // Define columns for the jobs table
  const columns: Column<SyncJob>[] = [
    {
      header: "Created At",
      cell: (job) => format(new Date(job.created_at), "MMM d, yyyy HH:mm"),
      className: "font-medium",
    },
    {
      header: "Completed At",
      cell: (job) => job.completed_at
        ? format(new Date(job.completed_at), "MMM d, yyyy HH:mm")
        : '-',
    },
    {
      header: "Status",
      cell: (job) => (
        <span
          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${job.status === "completed"
            ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
            : job.status === "failed"
              ? "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
              : job.status === "running"
                ? "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300"
                : "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300"
            }`}
        >
          {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
        </span>
      ),
    },
    {
      header: "Error",
      cell: (job) => (
        <div className="max-w-md truncate">
          {job.error || '-'}
        </div>
      ),
    },
  ];

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

      <DataTable
        data={filteredJobs}
        columns={columns}
        isLoading={isLoading}
        searchPlaceholder="Search by status..."
        searchValue={search}
        onSearchChange={setSearch}
        onRowClick={(job) => onJobSelect(job.id)}
        emptyMessage="No sync jobs found"
      />
    </div>
  );
};
