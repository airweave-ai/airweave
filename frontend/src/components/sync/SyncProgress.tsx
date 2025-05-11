import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Clock, MessageSquare, X } from "lucide-react";
import { useSyncSubscription } from "@/hooks/useSyncSubscription";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { format } from "date-fns";
import { SyncJob } from "@/types/sync";

/**
 * Four key metrics as per pubsub:
 * - inserted
 * - updated
 * - kept
 * - deleted
 */

interface SyncProgressProps {
  syncId: string | null;
  syncJobId: string | null;
  onClose?: () => void;
  lastSync?: SyncJob | null;
  isLive?: boolean; // New prop to indicate if this is a live view in the main UI
}

export const SyncProgress = ({ syncId, syncJobId, lastSync, onClose, isLive = false }: SyncProgressProps) => {
  const navigate = useNavigate();
  const updates = useSyncSubscription(isLive ? syncJobId : null);
  const latestUpdate = updates[updates.length - 1];

  // Use lastSync for completed/failed jobs, SSE updates for running jobs
  const useDbValues = !isLive && lastSync;

  // Prioritize SSE data for running jobs, fall back to database data for completed/failed
  const inserted = isLive ? (latestUpdate?.inserted ?? 0) : (lastSync?.entities_inserted ?? 0);
  const updated = isLive ? (latestUpdate?.updated ?? 0) : (lastSync?.entities_updated ?? 0);
  const kept = isLive ? (latestUpdate?.kept ?? 0) : (lastSync?.entities_kept ?? 0);
  const deleted = isLive ? (latestUpdate?.deleted ?? 0) : (lastSync?.entities_deleted ?? 0);
  const skipped = isLive ? (latestUpdate?.skipped ?? 0) : (lastSync?.entities_skipped ?? 0);

  const started_at = isLive
    ? (latestUpdate?.started_at || "Now")
    : (lastSync?.started_at || "Unknown");

  const isComplete = (lastSync?.status === 'completed') || (latestUpdate?.is_complete === true);
  const isFailed = (lastSync?.status === 'failed') || (latestUpdate?.is_failed === true);

  const isRunning = isLive && (!latestUpdate || (!latestUpdate.is_complete && !latestUpdate.is_failed));

  // Calculate total for normalized bar
  const total = inserted + updated + kept + deleted + skipped;

  // Build segment percentages
  // We guard against total being 0 (avoid NaN)
  const insertedPct = total > 0 ? (inserted / total) * 100 : 0;
  const updatedPct = total > 0 ? (updated / total) * 100 : 0;
  const keptPct = total > 0 ? (kept / total) * 100 : 0;
  const deletedPct = total > 0 ? (deleted / total) * 100 : 0;
  const skippedPct = total > 0 ? (skipped / total) * 100 : 0;

  const handleTryChat = () => {
    navigate("/chat", {
      state: {
        showCreateDialog: true,
        preselectedSyncId: syncId
      }
    });
  };

  return (
    <Card className={`w-full max-w-none shadow-sm relative overflow-hidden ${isRunning ? 'live-pulsing-bg' : ''}`}>
      {/* Pulsing background effect when running */}
      {isRunning && (
        <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-primary/10 to-primary/5 animate-pulse-slow pointer-events-none" />
      )}

      <CardHeader className="pb-2 relative z-10">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            {isRunning ? (
              <>
                <div className="relative">
                  <div className="w-3 h-3 rounded-full bg-red-500 absolute animate-ping opacity-75"></div>
                  <div className="w-3 h-3 rounded-full bg-red-500 relative"></div>
                </div>
                <CardTitle>Live Sync Progress</CardTitle>
              </>
            ) : isComplete ? (
              <>
                <CheckCircle2 className="h-6 w-6 text-green-500" />
                <CardTitle>Sync Complete</CardTitle>
              </>
            ) : isFailed ? (
              <>
                <X className="h-6 w-6 text-destructive" />
                <CardTitle>Sync Failed</CardTitle>
              </>
            ) : (
              <>
                <Clock className="h-6 w-6 text-amber-500" />
                <CardTitle>Unknown State</CardTitle>
              </>
            )}
          </div>
          <div className="text-sm text-muted-foreground">
            Started at: {started_at === 'Now' || started_at === 'Unknown' || !started_at
              ? started_at || 'Now'
              : format(new Date(started_at), 'MMM d, yyyy h:mm:ss a')}
          </div>
        </div>
        <CardDescription>
          {isRunning ? (
            "Processing and embedding your data"
          ) : isComplete ? (
            <span>Successfully processed <span className="font-semibold">{total.toLocaleString()}</span> items</span>
          ) : (
            "The sync job failed. Please check the logs or try again."
          )}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 relative z-10">
        {/* Normalized multi-segment progress bar */}
        <div className="relative w-full h-3 bg-secondary/20 rounded-md overflow-hidden">
          <div
            className="absolute left-0 top-0 h-3 bg-green-500"
            style={{ width: `${insertedPct}%` }}
          />
          <div
            className="absolute top-0 h-3 bg-cyan-500"
            style={{ left: `${insertedPct}%`, width: `${updatedPct}%` }}
          />
          <div
            className="absolute top-0 h-3 bg-primary"
            style={{ left: `${insertedPct + updatedPct}%`, width: `${keptPct}%` }}
          />
          <div
            className="absolute top-0 h-3 bg-red-500"
            style={{ left: `${insertedPct + updatedPct + keptPct}%`, width: `${deletedPct}%` }}
          />
          <div
            className="absolute top-0 h-3 bg-yellow-500"
            style={{ left: `${insertedPct + updatedPct + keptPct + deletedPct}%`, width: `${skippedPct}%` }}
          />
        </div>

        {/* Legend */}
        <div className="text-xs mt-2 flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center space-x-1">
            <span className="w-3 h-3 block bg-green-500 rounded-full" />
            <span>Inserted</span>
          </div>
          <div className="flex items-center space-x-1">
            <span className="w-3 h-3 block bg-cyan-500 rounded-full" />
            <span>Updated</span>
          </div>
          <div className="flex items-center space-x-1">
            <span className="w-3 h-3 block bg-primary rounded-full" />
            <span>Kept</span>
          </div>
          <div className="flex items-center space-x-1">
            <span className="w-3 h-3 block bg-red-500 rounded-full" />
            <span>Deleted</span>
          </div>
          <div className="flex items-center space-x-1">
            <span className="w-3 h-3 block bg-yellow-500 rounded-full" />
            <span>Skipped</span>
          </div>
        </div>

        {/* Tally so far */}
        <div className="space-y-2 text-sm mt-4">
          <div className="flex justify-between">
            <span>Inserted</span>
            <span>{inserted.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span>Updated</span>
            <span>{updated.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span>Kept</span>
            <span>{kept.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span>Deleted</span>
            <span>{deleted.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span>Skipped</span>
            <span>{skipped.toLocaleString()}</span>
          </div>
        </div>
      </CardContent>

      {isComplete && (
        <CardFooter className="pt-0 relative z-10">
          <div className="w-full flex justify-end">
            <Button onClick={handleTryChat} className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4" />
              Chat with your synced data
            </Button>
          </div>
        </CardFooter>
      )}
    </Card>
  );
};
