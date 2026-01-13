import { Loader2 } from "lucide-react";
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
        {totalProcessed.toLocaleString()} synced
      </span>
    </p>
  );
}
