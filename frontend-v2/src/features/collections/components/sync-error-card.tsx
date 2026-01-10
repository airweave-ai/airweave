/**
 * SyncErrorCard - Display sync error information
 */

import { AlertCircle } from "lucide-react";

import { cn } from "@/lib/utils";

interface SyncErrorCardProps {
  error: string;
  className?: string;
}

export function SyncErrorCard({ error, className }: SyncErrorCardProps) {
  return (
    <div
      className={cn(
        "border-destructive/50 bg-destructive/10 rounded-lg border p-4",
        className
      )}
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="text-destructive mt-0.5 size-5 flex-shrink-0" />
        <div className="flex-1 space-y-1">
          <p className="text-destructive text-sm font-medium">Sync Failed</p>
          <p className="text-destructive/80 text-sm">{error}</p>
        </div>
      </div>
    </div>
  );
}
