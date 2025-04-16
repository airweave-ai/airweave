import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Clock, MessageSquare, X } from "lucide-react";
import { useSyncSubscription } from "@/hooks/useSyncSubscription";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { format } from "date-fns";

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
  isLive?: boolean; // New prop to indicate if this is a live view in the main UI
  startedAt?: string | null; // Pass the started_at timestamp for live views
}

export const SyncProgress = ({ syncId, syncJobId, onClose, isLive = false, startedAt }: SyncProgressProps) => {
  const navigate = useNavigate();
  const updates = useSyncSubscription(syncJobId);
  const latestUpdate = updates[updates.length - 1];
  const isRunning = !latestUpdate?.is_complete && (isLive || false);

  // Compute our four values
  const inserted = latestUpdate?.inserted || 0;
  const updated = latestUpdate?.updated || 0;
  const kept = latestUpdate?.kept || 0;
  const deleted = latestUpdate?.deleted || 0;

  // Calculate total for normalized bar
  const total = inserted + updated + kept + deleted;

  // Build segment percentages
  // We guard against total being 0 (avoid NaN)
  const insertedPct = total > 0 ? (inserted / total) * 100 : 0;
  const updatedPct = total > 0 ? (updated / total) * 100 : 0;
  const keptPct = total > 0 ? (kept / total) * 100 : 0;
  const deletedPct = total > 0 ? (deleted / total) * 100 : 0;

  const handleViewSchedule = () => {
    navigate("/sync/schedule");
  };

  const handleTryChat = () => {
    navigate("/chat", {
      state: {
        showCreateDialog: true,
        preselectedSyncId: syncId
      }
    });
  };

  // If this is a live view used in the main UI, we use a different layout
  if (isLive) {
    return (
      <Card className={`w-full max-w-none shadow-sm relative overflow-hidden ${isRunning ? 'live-pulsing-bg' : ''}`}>
        {/* Pulsing background effect when running */}
        {isRunning && (
          <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-primary/10 to-primary/5 animate-pulse-slow pointer-events-none" />
        )}

        <CardHeader className="pb-2 relative z-10">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <div className="relative">
                <div className="w-3 h-3 rounded-full bg-red-500 absolute animate-ping opacity-75"></div>
                <div className="w-3 h-3 rounded-full bg-red-500 relative"></div>
              </div>
              <CardTitle>Live Sync Progress</CardTitle>
            </div>
            <div className="text-sm text-muted-foreground">
              Started at: {startedAt ? format(new Date(startedAt), 'h:mm:ss a') : 'Now'}
            </div>
          </div>
          <CardDescription>Processing and embedding your data</CardDescription>
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
          </div>
        </CardContent>
      </Card>
    );
  }

  if (latestUpdate?.is_complete) {
    return (
      <Card className="w-full max-w-md mx-auto relative">
        <Button
          variant="ghost"
          size="icon"
          className="absolute right-2 top-2"
          onClick={() => onClose?.()}
        >
          <X className="h-4 w-4" />
        </Button>
        <CardHeader>
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="h-6 w-6 text-green-500" />
            <CardTitle>Sync Complete!</CardTitle>
          </div>
          <CardDescription>
            Successfully processed {(inserted + updated + kept + deleted).toLocaleString()} items
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Final tally */}
          <div className="grid grid-cols-4 gap-4 text-center">
            <div className="space-y-1">
              <div className="text-2xl font-bold text-green-500">+{inserted}</div>
              <div className="text-sm text-muted-foreground">Inserted</div>
            </div>
            <div className="space-y-1">
              <div className="text-2xl font-bold text-cyan-500">+{updated}</div>
              <div className="text-sm text-muted-foreground">Updated</div>
            </div>
            <div className="space-y-1">
              <div className="text-2xl font-bold text-blue-600">{kept}</div>
              <div className="text-sm text-muted-foreground">Kept</div>
            </div>
            <div className="space-y-1">
              <div className="text-2xl font-bold text-red-500">-{deleted}</div>
              <div className="text-sm text-muted-foreground">Deleted</div>
            </div>
          </div>
        </CardContent>
        <CardFooter className="flex flex-col gap-3">
          <Button onClick={handleTryChat} className="w-full">
            <MessageSquare className="mr-2 h-4 w-4" />
            Try out in chat
          </Button>
          <Button onClick={handleViewSchedule} variant="outline" className="w-full">
            <Clock className="mr-2 h-4 w-4" />
            Schedule Next Sync
          </Button>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-md mx-auto relative">
      <Button
        variant="ghost"
        size="icon"
        className="absolute right-2 top-2"
        onClick={() => onClose?.()}
      >
        <X className="h-4 w-4" />
      </Button>
      <CardHeader>
        <CardTitle>Syncing Data</CardTitle>
        <CardDescription>Processing and embedding your data</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
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
        </div>

        {/* Tally so far (optional display if desired) */}
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
        </div>
      </CardContent>
    </Card>
  );
};
