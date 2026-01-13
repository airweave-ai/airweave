import type { SyncProgressUpdate } from "../lib/types";

interface SyncProgressIndicatorProps {
  progress: SyncProgressUpdate;
}

export function SyncProgressIndicator({
  progress,
}: SyncProgressIndicatorProps) {
  const totalProcessed =
    progress.entities_inserted +
    progress.entities_updated +
    progress.entities_deleted +
    progress.entities_kept +
    progress.entities_skipped;

  return (
    <div className="flex flex-col gap-1.5 w-full">
      <div
        className="h-1 rounded-full overflow-hidden"
        style={{ backgroundColor: "var(--connect-border)" }}
      >
        <div
          className="h-full rounded-full animate-progress-indeterminate"
          style={{
            backgroundColor: "var(--connect-primary)",
            width: "30%",
          }}
        />
      </div>

      <div
        className="flex items-center gap-2 text-xs flex-wrap"
        style={{ color: "var(--connect-text-muted)" }}
      >
        <span className="tabular-nums">
          {totalProcessed.toLocaleString()} synced
        </span>
        {progress.entities_inserted > 0 && (
          <span className="tabular-nums text-green-500">
            +{progress.entities_inserted.toLocaleString()}
          </span>
        )}
        {progress.entities_updated > 0 && (
          <span className="tabular-nums text-blue-500">
            ~{progress.entities_updated.toLocaleString()}
          </span>
        )}
        {progress.entities_deleted > 0 && (
          <span className="tabular-nums text-red-500">
            -{progress.entities_deleted.toLocaleString()}
          </span>
        )}
      </div>
    </div>
  );
}
