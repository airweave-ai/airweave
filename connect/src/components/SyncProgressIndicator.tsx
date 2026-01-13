import NumberFlow from "@number-flow/react";
import { AlertCircle, Loader2 } from "lucide-react";
import type { SyncProgressUpdate } from "../lib/types";

interface SyncProgressIndicatorProps {
  progress: SyncProgressUpdate;
  baseCount?: number;
}

export function SyncProgressIndicator({
  progress,
  baseCount = 0,
}: SyncProgressIndicatorProps) {
  const totalProcessed =
    baseCount +
    progress.entities_inserted +
    progress.entities_updated +
    progress.entities_kept +
    progress.entities_skipped;

  // Show error state when sync has failed
  if (progress.is_failed) {
    return (
      <p
        className="flex items-center gap-1.5 text-xs"
        style={{ color: "var(--connect-error)" }}
      >
        <AlertCircle size={12} />
        <span>{progress.error || "Sync failed"}</span>
      </p>
    );
  }

  return (
    <p
      className="flex items-center gap-1.5 text-xs"
      style={{ color: "var(--connect-text-muted)" }}
    >
      <Loader2
        size={12}
        className="animate-spin"
        style={{ color: "var(--connect-primary)" }}
      />
      <span className="tabular-nums">
        <NumberFlow value={totalProcessed} /> synced
      </span>
    </p>
  );
}
