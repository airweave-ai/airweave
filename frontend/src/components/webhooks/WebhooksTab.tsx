import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Check,
  ChevronDown,
  Copy,
  Eye,
  EyeOff,
  Loader2,
  Plus,
  Trash2,
  Webhook,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  useSubscription,
  useSubscriptionSecret,
  useCreateSubscription,
  useUpdateSubscription,
  useDeleteSubscription,
  useDeleteSubscriptions,
  type Subscription,
  type MessageAttempt,
  type CreateSubscriptionRequest,
} from "@/hooks/use-webhooks";
import { EVENT_TYPES_CONFIG, type EventTypeGroup, getEventTypeLabel, formatTimestamp } from "./shared";

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
    <div className="h-[200px] overflow-auto border rounded-lg p-2 bg-muted/30">
      {(Object.keys(EVENT_TYPES_CONFIG) as EventTypeGroup[]).map((group) => {
        const config = EVENT_TYPES_CONFIG[group];
        const isExpanded = expandedGroups.has(group);

        return (
          <div key={group}>
            <div
              className="flex items-center gap-2 py-1.5 px-2 cursor-pointer hover:bg-muted/50 rounded transition-colors"
              onClick={() => toggleGroup(group)}
            >
              <ChevronDown
                className={cn(
                  "size-3.5 text-muted-foreground transition-transform",
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
              />
              <span className="text-sm">{config.label}</span>
            </div>
            {isExpanded && (
              <div className="ml-5 space-y-0.5">
                {config.events.map((event) => (
                  <label
                    key={event.id}
                    className="flex items-center gap-2 py-1 pl-4 cursor-pointer hover:bg-muted/50 rounded transition-colors"
                  >
                    <Checkbox
                      checked={selectedEventTypes.includes(event.id)}
                      onCheckedChange={() => toggleEventSelection(event.id)}
                    />
                    <span className="text-sm font-mono text-muted-foreground">
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
  const { data: secretData, isLoading, refetch } = useSubscriptionSecret(subscriptionId, isRevealed);

  const handleReveal = () => {
    if (isRevealed) {
      setIsRevealed(false);
    } else {
      setIsRevealed(true);
      if (!secretData) refetch();
    }
  };

  const handleCopy = async () => {
    if (!secretData?.key) return;
    await navigator.clipboard.writeText(secretData.key);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <div className="space-y-1.5">
      <Label className="text-xs">Signing Secret</Label>
      <div className="flex items-center gap-1.5">
        <div className="flex-1 bg-muted/50 rounded-lg border px-2.5 py-1.5 overflow-hidden">
          <span className="block truncate font-mono text-xs">
            {isRevealed && secretData?.key
              ? secretData.key
              : "••••••••••••••••••••••••••••••••"}
          </span>
        </div>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={handleCopy}
          disabled={!secretData?.key}
        >
          {isCopied ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={handleReveal}
          disabled={isLoading}
        >
          {isLoading ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : isRevealed ? (
            <EyeOff className="size-3.5" />
          ) : (
            <Eye className="size-3.5" />
          )}
        </Button>
      </div>
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

  const secretError = validateWebhookSecret(secret);
  const isValid = url && selectedEventTypes.length > 0 && !secretError;

  const handleCreate = async () => {
    const request: CreateSubscriptionRequest = {
      url,
      event_types: selectedEventTypes,
      ...(secret ? { secret: formatSecretForApi(secret) } : {}),
    };
    await createMutation.mutateAsync(request);
    onOpenChange(false);
    resetForm();
  };

  const resetForm = () => {
    setUrl("");
    setSelectedEventTypes([]);
    setSecret("");
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) resetForm();
    onOpenChange(open);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Create Webhook</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label className="text-xs">Webhook URL</Label>
            <Input
              type="url"
              placeholder="https://example.com/webhook"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="h-9"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Event Types</Label>
            <EventTypeSelector
              selectedEventTypes={selectedEventTypes}
              onSelectionChange={setSelectedEventTypes}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">
              Signing Secret <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Input
              type="text"
              placeholder="Leave empty to auto-generate"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              className={cn("h-9", secretError && "border-destructive")}
            />
            {secretError && (
              <p className="text-xs text-destructive">{secretError}</p>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)} size="sm">
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={!isValid || createMutation.isPending} size="sm">
            {createMutation.isPending && <Loader2 className="mr-1.5 size-3.5 animate-spin" />}
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

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

  const [url, setUrl] = useState("");
  const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>([]);
  const [hasInitialized, setHasInitialized] = useState(false);

  if (data && !hasInitialized) {
    setUrl(data.endpoint.url);
    setSelectedEventTypes(data.endpoint.channels || []);
    setHasInitialized(true);
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      setHasInitialized(false);
      setUrl("");
      setSelectedEventTypes([]);
    }
    onOpenChange(newOpen);
  };

  const handleUpdate = async () => {
    if (!subscriptionId) return;
    await updateMutation.mutateAsync({
      id: subscriptionId,
      data: { url, event_types: selectedEventTypes },
    });
    handleOpenChange(false);
  };

  const handleDelete = async () => {
    if (!subscriptionId) return;
    await deleteMutation.mutateAsync(subscriptionId);
    handleOpenChange(false);
  };

  if (!subscriptionId) return null;

  const isValid = url && selectedEventTypes.length > 0;
  const isPending = updateMutation.isPending || deleteMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Webhook</DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <>
            <div className="space-y-4 py-2">
              <div className="space-y-1.5">
                <Label className="text-xs">Webhook URL</Label>
                <Input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  className={cn("h-9", urlError && "border-destructive")}
                />
                {urlError && (
                  <p className="text-xs text-destructive">{urlError}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Event Types</Label>
                <EventTypeSelector
                  selectedEventTypes={selectedEventTypes}
                  onSelectionChange={setSelectedEventTypes}
                />
              </div>
              <SecretField subscriptionId={subscriptionId} />
            </div>
            <DialogFooter className="flex-row justify-between sm:justify-between">
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={isPending}
                size="sm"
              >
                {deleteMutation.isPending && <Loader2 className="mr-1.5 size-3.5 animate-spin" />}
                Delete
              </Button>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => handleOpenChange(false)} size="sm">
                  Cancel
                </Button>
                <Button onClick={handleUpdate} disabled={!isValid || isPending} size="sm">
                  {updateMutation.isPending && <Loader2 className="mr-1.5 size-3.5 animate-spin" />}
                  Update
                </Button>
              </div>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ============ Empty State ============

function EmptyState({ onCreateClick }: { onCreateClick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="rounded-full bg-muted p-4 mb-4">
        <Webhook className="size-6 text-muted-foreground" />
      </div>
      <h3 className="font-medium mb-1">No webhooks yet</h3>
      <p className="text-sm text-muted-foreground text-center mb-4 max-w-xs">
        Create a webhook endpoint to receive event notifications.
      </p>
      <Button onClick={onCreateClick} size="sm">
        <Plus className="mr-1.5 size-3.5" />
        Create Webhook
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
                  <div className="flex flex-wrap gap-1">
                    {(subscription.channels || []).slice(0, 2).map((ch) => (
                      <Badge key={ch} variant="secondary" className="text-xs font-normal">
                        {getEventTypeLabel(ch)}
                      </Badge>
                    ))}
                    {(subscription.channels?.length || 0) > 2 && (
                      <Badge variant="secondary" className="text-xs font-normal">
                        +{(subscription.channels?.length || 0) - 2}
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
