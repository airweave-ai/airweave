import { Plug, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { SourceConnection } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useUsageChecks } from "@/stores/usage-store";

import { getAppIconUrl } from "../utils/helpers";

interface SourceConnectionsListProps {
  sourceConnections: SourceConnection[];
  selectedConnectionId: string | null;
  onSelectConnection: (id: string) => void;
  onAddSource: () => void;
}

function getConnectionStatusIndicator(connection: SourceConnection) {
  const isFederated = connection.federated_search === true;
  let colorClass = "bg-gray-400";
  let status = "unknown";
  let isAnimated = false;

  if (isFederated) {
    switch (connection.status) {
      case "pending_auth":
        colorClass = "bg-cyan-500";
        status = "Authentication required";
        break;
      case "error":
        colorClass = "bg-red-500";
        status = "Connection error";
        break;
      case "inactive":
        colorClass = "bg-gray-400";
        status = "Inactive";
        break;
      case "active":
      default:
        colorClass = "bg-green-500";
        status = "Ready for real-time search";
        break;
    }
  } else {
    switch (connection.status) {
      case "pending_auth":
        colorClass = "bg-cyan-500";
        status = "Authentication required";
        break;
      case "syncing":
        colorClass = "bg-blue-500";
        status = "Syncing";
        isAnimated = true;
        break;
      case "error":
        colorClass = "bg-red-500";
        status = "Sync failed";
        break;
      case "active":
        colorClass = "bg-green-500";
        status = "Active";
        break;
      case "inactive":
        colorClass = "bg-gray-400";
        status = "Inactive";
        break;
      default:
        colorClass = "bg-gray-400";
        status = "Unknown";
    }
  }

  return (
    <span
      className={cn(
        "inline-flex size-2 rounded-full opacity-80",
        colorClass,
        isAnimated && "animate-pulse"
      )}
      title={status}
    />
  );
}

export function SourceConnectionsList({
  sourceConnections,
  selectedConnectionId,
  onSelectConnection,
  onAddSource,
}: SourceConnectionsListProps) {
  const { sourceConnectionsAllowed, sourceConnectionsStatus } =
    useUsageChecks();
  const addSourceDisabledMessage =
    sourceConnectionsStatus?.details?.message || "Usage limit reached";

  if (sourceConnections.length === 0) {
    return (
      <EmptyState
        icon={<Plug strokeWidth={1.5} />}
        title="No sources connected"
        description="Connect your first data source to start syncing and searching your data"
        className="rounded-lg border-2 border-dashed py-12"
      >
        <TooltipProvider delayDuration={100}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button
                  variant="outline"
                  onClick={onAddSource}
                  disabled={!sourceConnectionsAllowed}
                  className="border-blue-500 bg-blue-50 text-blue-600 hover:border-blue-600 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-blue-500 dark:bg-blue-500/20 dark:text-blue-400 dark:hover:border-blue-400 dark:hover:bg-blue-500/30"
                >
                  <Plus className="mr-1.5 size-4" strokeWidth={2} />
                  Connect a source
                </Button>
              </span>
            </TooltipTrigger>
            {!sourceConnectionsAllowed && (
              <TooltipContent>
                <p>{addSourceDisabledMessage}</p>
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </EmptyState>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {sourceConnections.map((connection) => (
        <div
          key={connection.id}
          className={cn(
            "flex h-10 cursor-pointer items-center gap-2 overflow-hidden rounded-md border px-3 py-2 transition-all",
            selectedConnectionId === connection.id
              ? "border-blue-500 bg-blue-500/10 shadow-lg ring-2 shadow-blue-500/20 ring-blue-500/30"
              : "border-border hover:bg-muted"
          )}
          onClick={() => onSelectConnection(connection.id)}
        >
          {getConnectionStatusIndicator(connection)}

          <div className="flex size-5 flex-shrink-0 items-center justify-center overflow-hidden rounded-md">
            <img
              src={getAppIconUrl(connection.short_name)}
              alt={connection.name}
              className="size-5 object-contain"
            />
          </div>
          <div className="min-w-0 flex-1">
            <span className="text-foreground block truncate text-sm font-medium">
              {connection.name}
            </span>
          </div>
          {connection.auth?.authenticated &&
            !connection.federated_search &&
            connection.entities?.total_entities != null && (
              <span className="text-muted-foreground ml-1 flex-shrink-0 text-xs tabular-nums">
                {connection.entities.total_entities.toLocaleString()}
              </span>
            )}
        </div>
      ))}

      <TooltipProvider delayDuration={100}>
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              className={cn(
                "flex h-10 items-center gap-2 overflow-hidden rounded-md border border-dashed px-3 py-2 transition-all",
                sourceConnectionsAllowed
                  ? "cursor-pointer border-blue-500/30 bg-blue-500/5 hover:border-blue-400/40 hover:bg-blue-500/15"
                  : "cursor-not-allowed border-gray-300/30 bg-gray-100/5 opacity-50"
              )}
              onClick={sourceConnectionsAllowed ? onAddSource : undefined}
            >
              <Plus
                className={cn(
                  "size-5",
                  sourceConnectionsAllowed ? "text-blue-500" : "text-gray-400"
                )}
                strokeWidth={1.5}
              />
              <span className="text-foreground text-sm font-medium">
                Add Source
              </span>
            </div>
          </TooltipTrigger>
          <TooltipContent>
            <p>
              {sourceConnectionsAllowed
                ? "Add a new source to this collection"
                : addSourceDisabledMessage}
            </p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}
