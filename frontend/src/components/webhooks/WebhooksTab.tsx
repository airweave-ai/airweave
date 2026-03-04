import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Loader2, Plus, Trash2, Webhook } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useDeleteSubscriptions, type Subscription, type HealthStatus } from "@/hooks/use-webhooks";
import { getEventTypeLabel } from "./shared";

// ============ Health Status Badge ============

const HEALTH_CONFIG: Record<
  HealthStatus,
  { label: string; dotClass: string; textClass: string; description: string }
> = {
  healthy: {
    label: "Delivering",
    dotClass: "bg-emerald-500",
    textClass: "text-emerald-600 dark:text-emerald-400",
    description: "All recent deliveries succeeded.",
  },
  degraded: {
    label: "Degraded",
    dotClass: "bg-amber-500",
    textClass: "text-amber-600 dark:text-amber-400",
    description: "Some recent deliveries failed. Check the logs for details.",
  },
  failing: {
    label: "Failing",
    dotClass: "bg-red-500",
    textClass: "text-red-600 dark:text-red-400",
    description: "Multiple consecutive deliveries have failed. Your endpoint may be down.",
  },
  unknown: {
    label: "No data",
    dotClass: "bg-muted-foreground/40",
    textClass: "text-muted-foreground/60",
    description: "No deliveries yet. Events will appear once a sync runs.",
  },
};

function HealthBadge({ status }: { status: HealthStatus }) {
  const config = HEALTH_CONFIG[status] || HEALTH_CONFIG.unknown;
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={`inline-flex items-center gap-1.5 text-xs font-normal cursor-default ${config.textClass}`}
          >
            <span className={`size-1.5 rounded-full ${config.dotClass}`} />
            {config.label}
          </span>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-[220px]">
          <p className="text-[11px] leading-relaxed">{config.description}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ============ Empty State ============

function EmptyState({ onCreateClick }: { onCreateClick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="rounded-full bg-muted p-4 mb-4">
        <Webhook className="size-6 text-muted-foreground" />
      </div>
      <h3 className="font-medium mb-1">No subscriptions yet</h3>
      <p className="text-sm text-muted-foreground text-center mb-4 max-w-xs">
        Create a subscription to receive webhook notifications.
      </p>
      <Button onClick={onCreateClick} size="sm">
        <Plus className="mr-1.5 size-3.5" />
        Add subscription
      </Button>
    </div>
  );
}

// ============ Main Component ============

export function WebhooksTab({
  subscriptions,
  onEdit,
  onCreateClick,
}: {
  subscriptions: Subscription[];
  onEdit: (subscription: Subscription) => void;
  onCreateClick: () => void;
}) {
  const deleteMutation = useDeleteSubscriptions();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    setSelectedIds(
      selectedIds.size === subscriptions.length
        ? new Set()
        : new Set(subscriptions.map((s) => s.id))
    );
  };

  const handleBulkDelete = async () => {
    await deleteMutation.mutateAsync(Array.from(selectedIds));
    setSelectedIds(new Set());
  };

  if (subscriptions.length === 0) {
    return <EmptyState onCreateClick={onCreateClick} />;
  }

  const allSelected = selectedIds.size === subscriptions.length;
  const someSelected = selectedIds.size > 0 && selectedIds.size < subscriptions.length;

  return (
    <div className="space-y-3">
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 p-2 bg-muted/50 rounded-lg border">
          <span className="text-xs text-muted-foreground">{selectedIds.size} selected</span>
          <Button
            variant="destructive"
            size="sm"
            onClick={handleBulkDelete}
            disabled={deleteMutation.isPending}
            className="h-7 text-xs"
          >
            {deleteMutation.isPending ? (
              <Loader2 className="mr-1 size-3 animate-spin" />
            ) : (
              <Trash2 className="mr-1 size-3" />
            )}
            Delete
          </Button>
        </div>
      )}

      <div className="border rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30 hover:bg-muted/30">
              <TableHead className="w-10">
                <Checkbox
                  checked={allSelected}
                  // @ts-expect-error - indeterminate is valid
                  indeterminate={someSelected}
                  onCheckedChange={toggleSelectAll}
                />
              </TableHead>
              <TableHead className="text-xs font-medium">URL</TableHead>
              <TableHead className="text-xs font-medium">Status</TableHead>
              <TableHead className="text-xs font-medium">Health</TableHead>
              <TableHead className="text-xs font-medium">Events</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {subscriptions.map((subscription) => (
              <TableRow
                key={subscription.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => onEdit(subscription)}
              >
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    checked={selectedIds.has(subscription.id)}
                    onCheckedChange={() => toggleSelect(subscription.id)}
                  />
                </TableCell>
                <TableCell className="font-mono text-xs max-w-[250px] truncate">
                  {subscription.url}
                </TableCell>
                <TableCell>
                  {subscription.disabled ? (
                    <span className="text-xs font-medium text-red-600 dark:text-red-400">
                      Disabled
                    </span>
                  ) : (
                    <span className="text-xs font-medium text-foreground/70">
                      Enabled
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <HealthBadge status={subscription.health_status || "unknown"} />
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {(subscription.filter_types || []).slice(0, 2).map((ch) => (
                      <Badge key={ch} variant="secondary" className="text-xs font-normal">
                        {getEventTypeLabel(ch)}
                      </Badge>
                    ))}
                    {(subscription.filter_types?.length || 0) > 2 && (
                      <Badge variant="secondary" className="text-xs font-normal">
                        +{(subscription.filter_types?.length || 0) - 2}
                      </Badge>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
