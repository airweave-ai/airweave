import React from "react";
import { SyncScheduleManager } from "./SyncScheduleManager";

interface SyncScheduleExampleProps {
  syncId: string;
}

export function SyncScheduleExample({ syncId }: SyncScheduleExampleProps) {
  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Sync Schedule Management</h2>
        <p className="text-muted-foreground">
          Configure how your sync should run. Choose between one-time,
          scheduled, or continuous sync.
        </p>
      </div>

      <SyncScheduleManager
        syncId={syncId}
        initialConfig={{ type: "one-time" }}
        onConfigChange={(config) => {
          console.log("Schedule config changed:", config);
        }}
      />

      <div className="text-sm text-muted-foreground text-center">
        <p>
          <strong>One-time:</strong> Manual sync triggered on demand
          <br />
          <strong>Scheduled:</strong> Automatic recurring sync at specified
          intervals
          <br />
          <strong>Continuous:</strong> Minute-level incremental sync via
          Temporal
        </p>
      </div>
    </div>
  );
}
