import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import {
  Check,
  ChevronDown,
  Copy,
  Eye,
  EyeOff,
  Info,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  useSubscription,
  useUpdateSubscription,
  useDeleteSubscription,
  useEnableEndpoint,
  useDisableEndpoint,
  type HealthStatus,
} from "@/hooks/use-webhooks";
import { toast } from "sonner";
import { EVENT_TYPES_CONFIG, type EventTypeGroup, formatFullDate } from "./shared";

// ============ Event Type Selector ============

function EventTypeSelector({
  selectedEventTypes,
  onSelectionChange,
}: {
  selectedEventTypes: string[];
  onSelectionChange: (eventTypes: string[]) => void;
}) {
  const [expandedGroups, setExpandedGroups] = useState<Set<EventTypeGroup>>(
    new Set(Object.keys(EVENT_TYPES_CONFIG) as EventTypeGroup[])
  );

  const toggleGroup = (group: EventTypeGroup) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) {
        next.delete(group);
      } else {
        next.add(group);
      }
      return next;
    });
  };

  const getGroupEventIds = (group: EventTypeGroup) =>
    EVENT_TYPES_CONFIG[group].events.map((e) => e.id);

  const isGroupFullySelected = (group: EventTypeGroup) =>
    getGroupEventIds(group).every((id) => selectedEventTypes.includes(id));

  const isGroupPartiallySelected = (group: EventTypeGroup) => {
    const ids = getGroupEventIds(group);
    const count = ids.filter((id) => selectedEventTypes.includes(id)).length;
    return count > 0 && count < ids.length;
  };

  const toggleGroupSelection = (group: EventTypeGroup) => {
    const ids = getGroupEventIds(group);
    if (isGroupFullySelected(group)) {
      onSelectionChange(selectedEventTypes.filter((id) => !ids.includes(id)));
    } else {
      onSelectionChange([...new Set([...selectedEventTypes, ...ids])]);
    }
  };

  const toggleEventSelection = (eventId: string) => {
    onSelectionChange(
      selectedEventTypes.includes(eventId)
        ? selectedEventTypes.filter((id) => id !== eventId)
        : [...selectedEventTypes, eventId]
    );
  };

  return (
    <div className="h-[380px] overflow-auto border rounded-lg">
      {(Object.keys(EVENT_TYPES_CONFIG) as EventTypeGroup[]).map((group) => {
        const config = EVENT_TYPES_CONFIG[group];
        const isExpanded = expandedGroups.has(group);

        return (
          <div key={group}>
            <div
              className="flex items-center gap-2.5 py-2 px-3 cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => toggleGroup(group)}
            >
              <ChevronDown
                className={cn(
                  "size-3.5 text-muted-foreground/60 transition-transform",
                  !isExpanded && "-rotate-90"
                )}
              />
              <Checkbox
                checked={isGroupFullySelected(group)}
                // @ts-expect-error - indeterminate is valid
                indeterminate={isGroupPartiallySelected(group)}
                onClick={(e) => {
                  e.stopPropagation();
                  toggleGroupSelection(group);
                }}
                className="size-4"
              />
              <span className="text-[13px] font-mono font-medium">{config.label}</span>
            </div>
            {isExpanded && (
              <div className="ml-6 border-l border-border/50">
                {config.events.map((event) => (
                  <label
                    key={event.id}
                    className="flex items-center gap-2.5 py-1.5 pl-4 pr-3 cursor-pointer hover:bg-muted/30 transition-colors"
                  >
                    <Checkbox
                      checked={selectedEventTypes.includes(event.id)}
                      onCheckedChange={() => toggleEventSelection(event.id)}
                      className="size-4"
                    />
                    <span className="text-[13px] font-mono text-muted-foreground">
                      {event.id}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ============ Secret Field ============

function SecretField({ subscriptionId }: { subscriptionId: string }) {
  const [isRevealed, setIsRevealed] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  // Only fetch with secret when revealed
  const { data, isLoading, refetch } = useSubscription(subscriptionId, isRevealed);
  const secret = data?.secret;

  const handleReveal = () => {
    if (isRevealed) {
      setIsRevealed(false);
    } else {
      setIsRevealed(true);
      if (!secret) refetch();
    }
  };

  const handleCopy = async () => {
    if (!secret) return;
    await navigator.clipboard.writeText(secret);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <div>
      <label className="text-[11px] text-muted-foreground/50 uppercase tracking-wide block mb-1.5">
        Signing secret
      </label>
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-muted/40 border rounded-md px-3 h-7 flex items-center overflow-hidden">
          <span className="block truncate font-mono text-[11px] text-muted-foreground">
            {isRevealed && secret
              ? secret
              : "••••••••••••••••••••••••••••••••"}
          </span>
        </div>
        <Button
          variant="outline"
          size="icon"
          onClick={handleCopy}
          disabled={!secret}
          className="h-7 w-7 shrink-0"
        >
          {isCopied ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
        </Button>
        <Button
          variant="outline"
          size="icon"
          onClick={handleReveal}
          disabled={isLoading}
          className="h-7 w-7 shrink-0"
        >
          {isLoading ? (
            <Loader2 className="size-3 animate-spin" />
          ) : isRevealed ? (
            <EyeOff className="size-3" />
          ) : (
            <Eye className="size-3" />
          )}
        </Button>
      </div>
    </div>
  );
}

// ============ Enable Confirm Dialog ============

function EnableConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  isPending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (withRecovery: boolean) => void;
  isPending: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[400px] p-6">
        <h3 className="text-[16px] font-semibold">Enable subscription</h3>
        <p className="text-[13px] text-muted-foreground mt-2 leading-relaxed">
          Would you also like to recover failed messages from the last 7 days?
        </p>
        <div className="flex justify-end gap-2 mt-6">
          <Button
            variant="outline"
            onClick={() => onConfirm(false)}
            disabled={isPending}
            size="sm"
            className="h-8 px-4 text-[12px]"
          >
            {isPending && <Loader2 className="mr-1.5 size-3 animate-spin" />}
            Enable only
          </Button>
          <Button
            onClick={() => onConfirm(true)}
            disabled={isPending}
            size="sm"
            className="h-8 px-4 text-[12px]"
          >
            {isPending && <Loader2 className="mr-1.5 size-3 animate-spin" />}
            Enable & recover
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ============ Health Status Display ============

const HEALTH_DISPLAY: Record<
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

// ============ Edit Modal ============

export function EditWebhookModal({
  subscriptionId,
  open,
  onOpenChange,
}: {
  subscriptionId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data, isLoading } = useSubscription(subscriptionId);
  const updateMutation = useUpdateSubscription();
  const deleteMutation = useDeleteSubscription();
  const enableMutation = useEnableEndpoint();
  const disableMutation = useDisableEndpoint();

  const [url, setUrl] = useState("");
  const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>([]);
  const [showEnableDialog, setShowEnableDialog] = useState(false);

  // Sync form state when modal opens or data changes
  useEffect(() => {
    if (open && data) {
      setUrl(data.url);
      setSelectedEventTypes(data.filter_types || []);
    }
  }, [open, data]);

  const handleUpdate = async () => {
    if (!subscriptionId) return;
    await updateMutation.mutateAsync({
      id: subscriptionId,
      data: { url, event_types: selectedEventTypes },
    });
    onOpenChange(false);
  };

  const handleDelete = async () => {
    if (!subscriptionId) return;
    await deleteMutation.mutateAsync(subscriptionId);
    onOpenChange(false);
  };

  const handleToggleStatus = async () => {
    if (!subscriptionId) return;

    if (isDisabled) {
      // Show confirmation dialog for enabling
      setShowEnableDialog(true);
    } else {
      // Disable directly
      try {
        await disableMutation.mutateAsync(subscriptionId);
        toast.success("Subscription disabled");
      } catch {
        toast.error("Failed to disable subscription");
      }
    }
  };

  const handleEnableConfirm = async (withRecovery: boolean) => {
    if (!subscriptionId) return;
    try {
      const recoverSince = withRecovery
        ? new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
        : undefined;

      await enableMutation.mutateAsync({ id: subscriptionId, recoverSince });
      toast.success(withRecovery ? "Subscription enabled. Recovering messages..." : "Subscription enabled");
      setShowEnableDialog(false);
    } catch {
      toast.error("Failed to enable subscription");
    }
  };

  if (!subscriptionId) return null;

  const subscription = data;
  const isDisabled = subscription?.disabled ?? false;
  const isValid = url && selectedEventTypes.length > 0;
  const isPending = updateMutation.isPending || deleteMutation.isPending;
  const isToggling = enableMutation.isPending || disableMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[940px] p-0 gap-0 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="size-5 animate-spin text-muted-foreground/40" />
          </div>
        ) : (
          <div className="grid grid-cols-[220px_1fr]">
            {/* Left - Metadata sidebar */}
            <div className="bg-muted/30 border-r border-border/40 p-6 space-y-6">
              <div>
                <p className="text-[11px] text-muted-foreground/50 uppercase tracking-wide mb-2">
                  Status
                </p>
                {isDisabled ? (
                  <span className="text-[13px] font-medium text-red-600 dark:text-red-400">
                    Disabled
                  </span>
                ) : (
                  <span className="text-[13px] font-medium text-foreground/70">
                    Enabled
                  </span>
                )}
              </div>

              <div>
                <p className="text-[11px] text-muted-foreground/50 uppercase tracking-wide mb-2">
                  Health
                </p>
                {(() => {
                  const healthStatus = (subscription?.health_status || "unknown") as HealthStatus;
                  const config = HEALTH_DISPLAY[healthStatus] || HEALTH_DISPLAY.unknown;
                  return (
                    <TooltipProvider delayDuration={200}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className={`inline-flex items-center gap-1.5 text-[13px] font-medium cursor-default ${config.textClass}`}>
                            <span className={`size-2 rounded-full ${config.dotClass}`} />
                            {config.label}
                            <Info className="size-3 text-muted-foreground/40" />
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-[220px]">
                          <p className="text-[11px] leading-relaxed">{config.description}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  );
                })()}
              </div>

              <div>
                <p className="text-[11px] text-muted-foreground/50 uppercase tracking-wide mb-2">
                  Subscription ID
                </p>
                <p className="text-[12px] font-mono text-muted-foreground/70 break-all leading-relaxed">
                  {subscription?.id}
                </p>
              </div>

              <div>
                <p className="text-[11px] text-muted-foreground/50 uppercase tracking-wide mb-2">
                  Created
                </p>
                <p className="text-[13px] text-muted-foreground/80">
                  {subscription?.created_at ? formatFullDate(subscription.created_at) : "—"}
                </p>
              </div>

              <div>
                <p className="text-[11px] text-muted-foreground/50 uppercase tracking-wide mb-2">
                  Last updated
                </p>
                <p className="text-[13px] text-muted-foreground/80">
                  {subscription?.updated_at ? formatFullDate(subscription.updated_at) : "—"}
                </p>
              </div>
            </div>

            {/* Right - Main content */}
            <div className="flex flex-col">
              <div className="px-6 pt-6 pb-5 border-b border-border/40">
                <h2 className="text-[18px] font-semibold tracking-tight">
                  Edit subscription
                </h2>
                <p className="text-[13px] text-muted-foreground/60 mt-1">
                  Configure your subscription URL and subscribed events.
                </p>
              </div>

              <div className="px-6 py-5 space-y-4 flex-1">
                <div>
                  <label className="text-[11px] text-muted-foreground/50 uppercase tracking-wide block mb-1.5">
                    URL
                  </label>
                  <input
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    className="w-full h-6 px-2 text-[11px] font-mono bg-muted/50 border border-border/50 rounded text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-ring"
                    placeholder="https://..."
                  />
                </div>

                <div className="flex-1">
                  <label className="text-[11px] text-muted-foreground/50 uppercase tracking-wide block mb-1.5">
                    Subscribed events
                  </label>
                  <EventTypeSelector
                    selectedEventTypes={selectedEventTypes}
                    onSelectionChange={setSelectedEventTypes}
                  />
                </div>

                <SecretField subscriptionId={subscriptionId} />
              </div>

              <div className="flex items-center justify-between px-6 py-4 border-t border-border/40 mt-auto">
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    onClick={handleDelete}
                    disabled={isPending}
                    size="sm"
                    className="h-8 px-3 text-[12px] text-red-600 hover:text-red-700 hover:bg-red-500/10 dark:text-red-400 dark:hover:text-red-300"
                  >
                    {deleteMutation.isPending && <Loader2 className="mr-1.5 size-3 animate-spin" />}
                    Delete
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={handleToggleStatus}
                    disabled={isToggling}
                    size="sm"
                    className="h-8 px-3 text-[12px] text-muted-foreground hover:text-foreground"
                  >
                    {isToggling && <Loader2 className="mr-1.5 size-3 animate-spin" />}
                    {isDisabled ? "Enable" : "Disable"}
                  </Button>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => onOpenChange(false)}
                    size="sm"
                    className="h-8 px-4 text-[12px]"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleUpdate}
                    disabled={!isValid || isPending}
                    size="sm"
                    className="h-8 px-5 text-[12px]"
                  >
                    {updateMutation.isPending && <Loader2 className="mr-1.5 size-3 animate-spin" />}
                    Save changes
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </DialogContent>

      <EnableConfirmDialog
        open={showEnableDialog}
        onOpenChange={setShowEnableDialog}
        onConfirm={handleEnableConfirm}
        isPending={enableMutation.isPending}
      />
    </Dialog>
  );
}
