// Sync Job Types

// Matches backend SyncJobStatus enum
export type SyncJobStatus =
  | "created"
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelling"
  | "cancelled";

// Sync job returned from GET /connect/source-connections/{id}/jobs
export interface SourceConnectionJob {
  source_connection_id: string;
  id: string;
  organization_id: string;
  created_by_email?: string | null;
  modified_by_email?: string | null;
  created_at?: string | null;
  modified_at?: string | null;
  status: SyncJobStatus;
  scheduled: boolean;
  entities_inserted?: number;
  entities_updated?: number;
  entities_deleted?: number;
  entities_kept?: number;
  entities_skipped?: number;
  entities_encountered?: Record<string, number>;
  started_at?: string | null;
  completed_at?: string | null;
  failed_at?: string | null;
  error?: string | null;
}

// Real-time sync progress update from SSE
export interface SyncProgressUpdate {
  entities_inserted: number;
  entities_updated: number;
  entities_deleted: number;
  entities_kept: number;
  entities_skipped: number;
  entities_encountered: Record<string, number>;
  is_complete?: boolean;
  is_failed?: boolean;
  error?: string;
}

// Sync subscription state for tracking active SSE connections
export interface SyncSubscription {
  connectionId: string;
  jobId: string;
  lastUpdate: SyncProgressUpdate;
  lastMessageTime: number;
  status: "active" | "completed" | "failed" | "reconnecting";
  reconnectAttempt?: number;
}
