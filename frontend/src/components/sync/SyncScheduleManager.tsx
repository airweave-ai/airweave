import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Play, Pause, Trash2, Save } from "lucide-react";
import { SyncSchedule, SyncScheduleConfig } from "./SyncSchedule";
import { useSyncSchedule } from "@/hooks/useSyncSchedule";
import { toast } from "sonner";

interface SyncScheduleManagerProps {
  syncId: string;
  initialConfig?: SyncScheduleConfig;
  onConfigChange?: (config: SyncScheduleConfig) => void;
}

export function SyncScheduleManager({
  syncId,
  initialConfig = { type: "one-time" },
  onConfigChange,
}: SyncScheduleManagerProps) {
  const [config, setConfig] = useState<SyncScheduleConfig>(initialConfig);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const {
    isLoading,
    currentSchedule,
    error,
    createSchedule,
    updateSchedule,
    pauseSchedule,
    resumeSchedule,
    deleteSchedule,
    loadSchedule,
    clearError,
  } = useSyncSchedule({ syncId });

  // Load existing schedule on mount
  useEffect(() => {
    loadSchedule();
  }, [loadSchedule]);

  // Handle config changes
  const handleConfigChange = (newConfig: SyncScheduleConfig) => {
    setConfig(newConfig);
    setHasUnsavedChanges(true);
    onConfigChange?.(newConfig);
  };

  // Handle save action
  const handleSave = async () => {
    if (config.type !== "incremental") {
      toast.info("One-time and scheduled syncs are handled differently", {
        description:
          "Incremental syncs use minute-level scheduling via Temporal",
      });
      return;
    }

    try {
      if (currentSchedule) {
        // Update existing schedule
        await updateSchedule(config);
      } else {
        // Create new schedule
        await createSchedule(config);
      }
      setHasUnsavedChanges(false);
    } catch (err) {
      // Error handling is done in the hook
      console.error("Save failed:", err);
    }
  };

  // Handle pause/resume
  const handleToggleSchedule = async () => {
    if (!currentSchedule) return;

    try {
      if (currentSchedule.is_active) {
        await pauseSchedule();
      } else {
        await resumeSchedule();
      }
    } catch (err) {
      console.error("Toggle schedule failed:", err);
    }
  };

  // Handle delete
  const handleDelete = async () => {
    if (!currentSchedule) return;

    try {
      await deleteSchedule();
      setConfig({ type: "one-time" });
      setHasUnsavedChanges(false);
    } catch (err) {
      console.error("Delete schedule failed:", err);
    }
  };

  // Get schedule status display
  const getScheduleStatus = () => {
    if (!currentSchedule) return null;

    return (
      <div className="flex items-center gap-2">
        <Badge variant={currentSchedule.is_active ? "default" : "secondary"}>
          {currentSchedule.is_active ? "Active" : "Paused"}
        </Badge>
        <span className="text-sm text-muted-foreground">
          Cron: {currentSchedule.cron_expression}
        </span>
      </div>
    );
  };

  // Get action buttons
  const getActionButtons = () => {
    if (config.type !== "incremental") {
      return null;
    }

    return (
      <div className="flex gap-2">
        {hasUnsavedChanges && (
          <Button onClick={handleSave} disabled={isLoading} size="sm">
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save Schedule
          </Button>
        )}

        {currentSchedule && (
          <>
            <Button
              onClick={handleToggleSchedule}
              disabled={isLoading}
              variant="outline"
              size="sm"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : currentSchedule.is_active ? (
                <Pause className="h-4 w-4" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {currentSchedule.is_active ? "Pause" : "Resume"}
            </Button>

            <Button
              onClick={handleDelete}
              disabled={isLoading}
              variant="destructive"
              size="sm"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Delete
            </Button>
          </>
        )}
      </div>
    );
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Sync Schedule</CardTitle>
          {getActionButtons()}
        </div>
        {getScheduleStatus()}
      </CardHeader>
      <CardContent>
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>
              {error}
              <Button
                variant="link"
                size="sm"
                onClick={clearError}
                className="p-0 h-auto ml-2"
              >
                Dismiss
              </Button>
            </AlertDescription>
          </Alert>
        )}

        <SyncSchedule value={config} onChange={handleConfigChange} />

        {config.type === "incremental" && currentSchedule && (
          <div className="mt-4 p-3 bg-muted rounded-md">
            <p className="text-sm text-muted-foreground">
              <strong>Current Schedule:</strong>{" "}
              {currentSchedule.cron_expression}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Status: {currentSchedule.is_active ? "Active" : "Paused"} •
              Created:{" "}
              {new Date(currentSchedule.created_at).toLocaleDateString()}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
