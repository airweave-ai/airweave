/**
 * EntityStateList - Display entity type counts and sync status
 */

import { FileText, Loader2, Play } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

interface EntityState {
  entity_type: string;
  total_count: number;
  last_updated_at?: string;
  sync_status: "pending" | "syncing" | "synced" | "failed";
}

interface EntityStateListProps {
  entityStates?: EntityState[];
  isRunning: boolean;
  isPending: boolean;
  onStartSync?: () => void;
  className?: string;
}

export function EntityStateList({
  entityStates = [],
  isRunning,
  isPending,
  onStartSync,
  className,
}: EntityStateListProps) {
  // Format entity type name for display
  const formatEntityType = (type: string): string => {
    return type
      .replace(/Entity$/, "")
      .replace(/([A-Z])/g, " $1")
      .trim();
  };

  // Get status indicator
  const getStatusIndicator = (status: EntityState["sync_status"]) => {
    switch (status) {
      case "syncing":
        return (
          <span className="inline-flex size-2 animate-pulse rounded-full bg-blue-500" />
        );
      case "synced":
        return (
          <span className="inline-flex size-2 rounded-full bg-green-500" />
        );
      case "failed":
        return <span className="inline-flex size-2 rounded-full bg-red-500" />;
      default:
        return <span className="inline-flex size-2 rounded-full bg-gray-400" />;
    }
  };

  // Empty state
  if (entityStates.length === 0) {
    return (
      <EmptyState
        icon={<FileText />}
        title="No entities synced"
        description="Start a sync to begin indexing your data"
        className={cn("rounded-lg border-2 border-dashed py-8", className)}
      >
        {onStartSync && (
          <Button
            variant="outline"
            size="sm"
            onClick={onStartSync}
            disabled={isRunning || isPending}
          >
            {isRunning || isPending ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Syncing...
              </>
            ) : (
              <>
                <Play className="mr-2 size-4" />
                Start Sync
              </>
            )}
          </Button>
        )}
      </EmptyState>
    );
  }

  // Calculate total entities
  const totalEntities = entityStates.reduce(
    (sum, state) => sum + state.total_count,
    0
  );

  return (
    <div className={cn("space-y-3", className)}>
      {/* Summary */}
      <div className="flex items-center justify-between">
        <div className="text-sm">
          <span className="text-muted-foreground">Total entities: </span>
          <span className="font-semibold">
            {totalEntities.toLocaleString()}
          </span>
        </div>
        {(isRunning || isPending) && (
          <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
            <Loader2 className="size-4 animate-spin" />
            <span>Syncing...</span>
          </div>
        )}
      </div>

      {/* Entity type list */}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {entityStates.map((state) => (
          <div
            key={state.entity_type}
            className="bg-card flex items-center justify-between rounded-lg border p-3"
          >
            <div className="flex items-center gap-2">
              {getStatusIndicator(state.sync_status)}
              <span className="text-sm font-medium">
                {formatEntityType(state.entity_type)}
              </span>
            </div>
            <span className="text-muted-foreground text-sm">
              {state.total_count.toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
