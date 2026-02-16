import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { AlertCircle, ChevronDown, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCreateSubscription, type CreateSubscriptionRequest } from "@/hooks/use-webhooks";
import { EVENT_TYPES_CONFIG, type EventTypeGroup } from "./shared";

// ============ Secret Validation ============

const MIN_SECRET_LENGTH = 24;
const MAX_SECRET_LENGTH = 75;

function validateWebhookSecret(secret: string): string | null {
  if (!secret) return null;
  if (secret.length < MIN_SECRET_LENGTH) {
    return `Secret must be at least ${MIN_SECRET_LENGTH} characters.`;
  }
  if (secret.length > MAX_SECRET_LENGTH) {
    return `Secret must be at most ${MAX_SECRET_LENGTH} characters.`;
  }
  return null;
}

function formatSecretForApi(secret: string): string {
  return `whsec_${btoa(secret)}`;
}

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

// ============ Create Modal ============

export function CreateWebhookModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createMutation = useCreateSubscription();
  const [url, setUrl] = useState("");
  const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>([]);
  const [secret, setSecret] = useState("");
  const [endpointError, setEndpointError] = useState<string | null>(null);

  const secretError = validateWebhookSecret(secret);
  const isValid = url && selectedEventTypes.length > 0 && !secretError;

  const handleUrlChange = (value: string) => {
    setUrl(value);
    if (endpointError) setEndpointError(null);
  };

  const handleCreate = async () => {
    setEndpointError(null);
    const request: CreateSubscriptionRequest = {
      url,
      event_types: selectedEventTypes,
      ...(secret ? { secret: formatSecretForApi(secret) } : {}),
    };
    try {
      await createMutation.mutateAsync(request);
      onOpenChange(false);
      resetForm();
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : "Failed to create webhook";
      setEndpointError(message);
    }
  };

  const resetForm = () => {
    setUrl("");
    setSelectedEventTypes([]);
    setSecret("");
    setEndpointError(null);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) resetForm();
    onOpenChange(open);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-[680px] p-0 gap-0 overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-6 pb-5 border-b border-border/40">
          <h2 className="text-[18px] font-semibold tracking-tight">
            Create subscription
          </h2>
          <p className="text-[13px] text-muted-foreground/60 mt-1">
            Set up a new subscription to receive webhook notifications.
          </p>
        </div>

        {/* Form fields */}
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="text-[11px] text-muted-foreground/50 uppercase tracking-wide block mb-1.5">
              URL
            </label>
            <Input
              type="url"
              placeholder="https://example.com/webhooks"
              value={url}
              onChange={(e) => handleUrlChange(e.target.value)}
              className={cn(
                "h-8 text-[12px] font-mono",
                endpointError && "border-destructive focus-visible:ring-destructive/30"
              )}
            />
            {endpointError && (
              <div className="mt-2 flex items-start gap-2 rounded-md bg-destructive/5 border border-destructive/20 px-3 py-2.5">
                <AlertCircle className="size-3.5 text-destructive shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="text-[12px] font-medium text-destructive">
                    Failed to create subscription
                  </p>
                  <p className="text-[11px] text-destructive/80 mt-0.5 leading-relaxed">
                    {endpointError}
                  </p>
                </div>
              </div>
            )}
          </div>

          <div>
            <label className="text-[11px] text-muted-foreground/50 uppercase tracking-wide block mb-1.5">
              Subscribed events
            </label>
            <EventTypeSelector
              selectedEventTypes={selectedEventTypes}
              onSelectionChange={setSelectedEventTypes}
            />
          </div>

          <div>
            <label className="text-[11px] text-muted-foreground/50 uppercase tracking-wide block mb-1.5">
              Signing secret{" "}
              <span className="normal-case text-muted-foreground/40">(optional, auto-generated if empty)</span>
            </label>
            <Input
              type="text"
              placeholder="Leave empty to auto-generate"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              className={cn("h-8 text-[12px] font-mono", secretError && "border-destructive")}
            />
            {secretError && (
              <p className="text-[11px] text-destructive mt-1">{secretError}</p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border/40">
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            size="sm"
            className="h-8 px-4 text-[12px]"
          >
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!isValid || createMutation.isPending}
            size="sm"
            className="h-8 px-5 text-[12px]"
          >
            {createMutation.isPending && <Loader2 className="mr-1.5 size-3 animate-spin" />}
            Create subscription
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
