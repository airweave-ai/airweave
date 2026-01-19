/**
 * SyncStatusDashboard - Displays sync status cards and action buttons
 */

import {
  Clock,
  History,
  Loader2,
  RefreshCw,
  Send,
  Settings,
  Square,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type SyncState = "IDLE" | "SYNCING" | "CANCELLING";

interface SyncStatusDisplayInfo {
  text: string;
  color: string;
  icon: "loader" | null;
}

interface SyncStatusDashboardProps {
  isFederatedSource: boolean;
  syncState: SyncState;
  isSyncing: boolean;
  entityCount: number;
  statusDisplay: SyncStatusDisplayInfo;
  scheduleCron?: string | null;
  scheduleNextRun?: string | null;
  lastSyncTime?: string | null;
  onSync: () => void;
  onCancelSync: () => void;
  onDelete: () => void;
  isSyncPending: boolean;
  isCancelPending: boolean;
}

export function SyncStatusDashboard({
  isFederatedSource,
  syncState,
  isSyncing,
  entityCount,
  statusDisplay,
  scheduleCron,
  scheduleNextRun,
  lastSyncTime,
  onSync,
  onCancelSync,
  onDelete,
  isSyncPending,
  isCancelPending,
}: SyncStatusDashboardProps) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex flex-wrap items-center gap-2">
        {/* Entities Card */}
        {!isFederatedSource && (
          <div className="bg-card flex h-8 min-w-[90px] items-center gap-2 rounded-md border px-3 py-1.5 shadow-sm">
            <span className="text-muted-foreground/60 text-[10px] font-medium tracking-wider uppercase">
              ENTITIES
            </span>
            <span className="text-foreground text-xs font-semibold">
              {entityCount.toLocaleString()}
            </span>
          </div>
        )}

        {/* Status Card */}
        <div
          className={cn(
            "flex h-8 min-w-[90px] items-center gap-2 rounded-md border px-3 py-1.5 shadow-sm",
            isSyncing
              ? "border-blue-700/50 bg-blue-900/30"
              : "border-border bg-card"
          )}
        >
          <span className="text-muted-foreground/60 text-[10px] font-medium tracking-wider uppercase">
            STATUS
          </span>
          <div className="flex items-center gap-1">
            {statusDisplay.icon === "loader" ? (
              <Loader2 className="size-3 animate-spin text-blue-500" />
            ) : (
              <span
                className={cn(
                  "inline-flex size-2 rounded-full",
                  statusDisplay.color
                )}
              />
            )}
            <span
              className={cn(
                "text-xs font-medium capitalize",
                isSyncing ? "text-blue-400" : "text-foreground"
              )}
            >
              {statusDisplay.text}
            </span>
          </div>
        </div>

        {/* Schedule Card */}
        {!isFederatedSource && scheduleCron && (
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="bg-card flex h-8 min-w-[100px] cursor-help items-center gap-2 rounded-md border px-3 py-1.5 shadow-sm">
                  <span className="text-muted-foreground/60 text-[10px] font-medium tracking-wider uppercase">
                    SCHEDULE
                  </span>
                  <div className="flex items-center gap-1">
                    <Clock className="text-muted-foreground size-3" />
                    <span className="text-foreground text-xs font-medium">
                      {scheduleCron}
                    </span>
                  </div>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p className="text-xs">
                  Next run: {scheduleNextRun || "Not scheduled"}
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}

        {/* Last Sync Card */}
        {!isFederatedSource && !isSyncing && lastSyncTime && (
          <div className="bg-card flex h-8 min-w-[100px] items-center gap-2 rounded-md border px-3 py-1.5 shadow-sm">
            <span className="text-muted-foreground/60 text-[10px] font-medium tracking-wider uppercase">
              LAST SYNC
            </span>
            <div className="flex items-center gap-1">
              <History className="text-muted-foreground size-3" />
              <span className="text-foreground text-xs font-medium">
                {lastSyncTime}
              </span>
            </div>
          </div>
        )}

        {/* Federated Search Indicator */}
        {isFederatedSource && (
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex h-8 cursor-help items-center gap-2 rounded-md border border-blue-800/30 bg-blue-900/20 px-3 py-1.5 shadow-sm">
                  <span className="text-muted-foreground/60 text-[10px] font-medium tracking-wider uppercase">
                    MODE
                  </span>
                  <div className="flex items-center gap-1">
                    <Send className="size-3 text-blue-500" />
                    <span className="text-xs font-medium text-blue-400">
                      Federated search
                    </span>
                  </div>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p className="max-w-[240px] text-xs">
                  Data is queried in real-time when you search instead of being
                  synced and indexed.
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-1.5">
        {/* Refresh/Cancel Button */}
        {!isFederatedSource && (
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className="size-8"
                  onClick={() => {
                    if (syncState === "IDLE") {
                      onSync();
                    } else if (syncState === "SYNCING") {
                      onCancelSync();
                    }
                  }}
                  disabled={
                    syncState === "CANCELLING" ||
                    isSyncPending ||
                    isCancelPending
                  }
                >
                  {syncState === "CANCELLING" || isCancelPending ? (
                    <Loader2 className="size-3 animate-spin text-orange-500" />
                  ) : syncState === "SYNCING" ? (
                    <Square className="size-3 text-red-500" />
                  ) : isSyncPending ? (
                    <Loader2 className="size-3 animate-spin" />
                  ) : (
                    <RefreshCw className="size-3" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {syncState === "CANCELLING"
                  ? "Cancelling sync..."
                  : syncState === "SYNCING"
                    ? "Cancel sync"
                    : "Refresh data"}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}

        {/* Settings Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="icon" className="size-8">
              <Settings className="size-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onClick={onDelete}
              className="text-destructive focus:text-destructive"
            >
              <Trash2 className="mr-2 size-4" />
              Delete Connection
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
