import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Eye,
  EyeOff,
  Filter,
  Loader2,
  Plus,
  Webhook,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePageHeader } from "@/components/ui/page-header";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  createSubscription,
  deleteSubscription,
  fetchEventMessages,
  fetchSubscription,
  fetchSubscriptions,
  fetchSubscriptionSecret,
  updateSubscription,
  type EventMessage,
  type MessageAttempt,
  type Subscription,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";

export const Route = createFileRoute("/$orgSlug/webhooks")({
  component: WebhooksPage,
});

function WebhooksDocs() {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Webhooks</h3>
      <p className="text-muted-foreground text-sm">
        Webhooks allow you to receive real-time notifications when events occur
        in your Airweave account.
      </p>
      <div className="space-y-2">
        <h4 className="text-sm font-medium">Supported Events</h4>
        <ul className="text-muted-foreground space-y-1 text-sm">
          <li>Sync completed</li>
          <li>Sync failed</li>
          <li>New entities added</li>
          <li>Connection status changed</li>
        </ul>
      </div>
    </div>
  );
}

function WebhooksCode() {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Webhook Payload</h3>
      <p className="text-muted-foreground text-sm">
        Example webhook payload structure:
      </p>
      <pre className="bg-muted overflow-auto rounded-lg p-3 text-xs">
        <code>{`{
  "event": "sync.completed",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "collection_id": "col_abc123",
    "source_connection_id": "src_xyz789",
    "entities_processed": 150,
    "duration_ms": 4500
  }
}`}</code>
      </pre>
    </div>
  );
}

function WebhooksHelp() {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Setting Up Webhooks</h3>
      <p className="text-muted-foreground text-sm">
        Webhooks are HTTP callbacks that receive POST requests when events
        occur.
      </p>
      <div className="bg-muted rounded-lg p-3">
        <h4 className="text-sm font-medium">Requirements</h4>
        <ul className="text-muted-foreground mt-1 space-y-1 text-xs">
          <li>HTTPS endpoint required</li>
          <li>Must respond with 2xx status</li>
          <li>Timeout: 30 seconds</li>
        </ul>
      </div>
    </div>
  );
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatFullTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function EventDetailModal({
  event,
  open,
  onOpenChange,
}: {
  event: EventMessage | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!event) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="font-mono">{event.eventType}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-3 text-sm">
            <div>
              <p className="text-muted-foreground text-xs uppercase">
                Event ID
              </p>
              <p className="font-mono break-all">{event.id}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs uppercase">
                Timestamp
              </p>
              <p>{formatFullTimestamp(event.timestamp)}</p>
            </div>
          </div>
          {event.channels && event.channels.length > 0 && (
            <div>
              <p className="text-muted-foreground mb-1 text-xs uppercase">
                Channels
              </p>
              <p className="text-sm">{event.channels.join(", ")}</p>
            </div>
          )}
          <div>
            <p className="text-muted-foreground mb-2 text-xs uppercase">
              Payload
            </p>
            <pre className="bg-muted max-h-[300px] overflow-auto rounded-lg p-4 text-xs">
              <code>{JSON.stringify(event.payload, null, 2)}</code>
            </pre>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Event types configuration - grouped by category
 */
const EVENT_TYPES_CONFIG = {
  sync: {
    label: "Sync Events",
    events: [
      { id: "sync.created", label: "Created" },
      { id: "sync.pending", label: "Pending" },
      { id: "sync.running", label: "Running" },
      { id: "sync.completed", label: "Completed" },
      { id: "sync.failed", label: "Failed" },
      { id: "sync.cancelling", label: "Cancelling" },
      { id: "sync.cancelled", label: "Cancelled" },
      { id: "sync.invalid", label: "Invalid" },
    ],
  },
} as const;

type EventTypeGroup = keyof typeof EVENT_TYPES_CONFIG;

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

  const getGroupEventIds = (group: EventTypeGroup): string[] => {
    return EVENT_TYPES_CONFIG[group].events.map((e) => e.id);
  };

  const isGroupFullySelected = (group: EventTypeGroup): boolean => {
    const groupEvents = getGroupEventIds(group);
    return groupEvents.every((id) => selectedEventTypes.includes(id));
  };

  const isGroupPartiallySelected = (group: EventTypeGroup): boolean => {
    const groupEvents = getGroupEventIds(group);
    const selectedCount = groupEvents.filter((id) =>
      selectedEventTypes.includes(id)
    ).length;
    return selectedCount > 0 && selectedCount < groupEvents.length;
  };

  const toggleGroupSelection = (group: EventTypeGroup) => {
    const groupEvents = getGroupEventIds(group);
    if (isGroupFullySelected(group)) {
      // Deselect all in group
      onSelectionChange(
        selectedEventTypes.filter((id) => !groupEvents.includes(id))
      );
    } else {
      // Select all in group
      const newSelection = new Set([...selectedEventTypes, ...groupEvents]);
      onSelectionChange(Array.from(newSelection));
    }
  };

  const toggleEventSelection = (eventId: string) => {
    if (selectedEventTypes.includes(eventId)) {
      onSelectionChange(selectedEventTypes.filter((id) => id !== eventId));
    } else {
      onSelectionChange([...selectedEventTypes, eventId]);
    }
  };

  return (
    <div className="max-h-[250px] overflow-auto">
      {(Object.keys(EVENT_TYPES_CONFIG) as EventTypeGroup[]).map((group) => {
        const config = EVENT_TYPES_CONFIG[group];
        const isExpanded = expandedGroups.has(group);
        const isFullySelected = isGroupFullySelected(group);
        const isPartiallySelected = isGroupPartiallySelected(group);

        return (
          <div key={group}>
            <div
              className="flex cursor-pointer items-center gap-2 py-1.5 hover:bg-muted/50"
              onClick={() => toggleGroup(group)}
            >
              {isExpanded ? (
                <ChevronDown className="text-muted-foreground size-4" />
              ) : (
                <ChevronRight className="text-muted-foreground size-4" />
              )}
              <Checkbox
                checked={isFullySelected}
                indeterminate={isPartiallySelected}
                onClick={(e) => {
                  e.stopPropagation();
                  toggleGroupSelection(group);
                }}
              />
              <span className="text-sm font-medium">{config.label}</span>
            </div>
            {isExpanded && (
              <div className="ml-6 space-y-1">
                {config.events.map((event) => (
                  <label
                    key={event.id}
                    className="flex cursor-pointer items-center gap-2 py-1 pl-4 hover:bg-muted/50"
                  >
                    <Checkbox
                      checked={selectedEventTypes.includes(event.id)}
                      onCheckedChange={() => toggleEventSelection(event.id)}
                    />
                    <span className="text-muted-foreground text-sm">
                      {event.label}
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

/**
 * Minimum length for a secret before base64 encoding.
 * Base64 encoding expands by ~4/3, so to get at least 32 chars after encoding,
 * we need at least 24 bytes (24 * 4/3 = 32).
 */
const MIN_SECRET_LENGTH = 24;

/**
 * Maximum length for a secret before base64 encoding.
 * Base64 encoding of 75 bytes = 100 chars (75 * 4/3 = 100).
 */
const MAX_SECRET_LENGTH = 75;

/**
 * Validates a webhook signing secret.
 * Returns null if valid, or an error message if invalid.
 */
function validateWebhookSecret(secret: string): string | null {
  if (!secret) return null; // Empty is valid (will be auto-generated)

  if (secret.length < MIN_SECRET_LENGTH) {
    return `Secret is too short. Must be at least ${MIN_SECRET_LENGTH} characters (currently ${secret.length}).`;
  }

  if (secret.length > MAX_SECRET_LENGTH) {
    return `Secret is too long. Must be at most ${MAX_SECRET_LENGTH} characters (currently ${secret.length}).`;
  }

  return null;
}

/**
 * Formats a secret for the Svix API by base64 encoding it and adding the prefix.
 */
function formatSecretForApi(secret: string): string {
  const base64Encoded = btoa(secret);
  return `whsec_${base64Encoded}`;
}

function CreateWebhookModal({
  open,
  onOpenChange,
  orgId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgId: string;
}) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>([]);
  const [secret, setSecret] = useState("");

  const secretValidationError = validateWebhookSecret(secret);

  const createMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return createSubscription(token, orgId, {
        url,
        event_types: selectedEventTypes,
        ...(secret ? { secret: formatSecretForApi(secret) } : {}),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.events.subscriptions(orgId),
      });
      onOpenChange(false);
      setUrl("");
      setSelectedEventTypes([]);
      setSecret("");
    },
  });

  const handleCreate = () => {
    createMutation.mutate();
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setUrl("");
      setSelectedEventTypes([]);
      setSecret("");
      createMutation.reset();
    }
    onOpenChange(open);
  };

  const isValid = url && selectedEventTypes.length > 0 && !secretValidationError;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Create Webhook</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="webhook-url">Webhook URL</Label>
            <Input
              id="webhook-url"
              type="url"
              placeholder="https://example.com/webhook"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <p className="text-muted-foreground text-xs">
              The URL that will receive webhook events via POST requests.
            </p>
          </div>
          <div className="space-y-2">
            <Label>Event Types</Label>
            <EventTypeSelector
              selectedEventTypes={selectedEventTypes}
              onSelectionChange={setSelectedEventTypes}
            />
            <p className="text-muted-foreground text-xs">
              Select at least one event type to receive.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="webhook-secret">
              Signing Secret{" "}
              <span className="text-muted-foreground font-normal">
                (optional)
              </span>
            </Label>
            <Input
              id="webhook-secret"
              type="text"
              placeholder="Leave empty to auto-generate (recommended)"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              className={secretValidationError ? "border-destructive" : ""}
            />
            {secretValidationError ? (
              <p className="text-destructive text-xs">{secretValidationError}</p>
            ) : secret ? (
              <p className="text-muted-foreground text-xs">
                Your secret will be base64 encoded and prefixed with
                &apos;whsec_&apos; before being stored.
              </p>
            ) : (
              <p className="text-muted-foreground text-xs">
                A secret key used to sign webhook payloads. If not provided, a
                secure secret will be automatically generated by the platform
                (recommended). Must be {MIN_SECRET_LENGTH}-{MAX_SECRET_LENGTH}{" "}
                characters.
              </p>
            )}
          </div>
          {createMutation.isError && (
            <p className="text-destructive text-sm">
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : "Failed to create webhook"}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!isValid || createMutation.isPending}
          >
            {createMutation.isPending ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Creating...
              </>
            ) : (
              "Create"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function getAttemptStatusBadge(statusCode: number) {
  if (statusCode >= 200 && statusCode < 300) {
    return (
      <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
        {statusCode}
      </span>
    );
  } else if (statusCode >= 400 && statusCode < 500) {
    return (
      <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">
        {statusCode}
      </span>
    );
  } else {
    return (
      <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
        {statusCode}
      </span>
    );
  }
}

function MessageAttemptsTable({ attempts }: { attempts: MessageAttempt[] }) {
  if (attempts.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        No delivery attempts yet.
      </p>
    );
  }

  return (
    <div className="max-h-[200px] overflow-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Status</TableHead>
            <TableHead>Message ID</TableHead>
            <TableHead className="text-right">Timestamp</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {attempts.map((attempt) => (
            <TableRow key={attempt.id}>
              <TableCell>
                {getAttemptStatusBadge(attempt.responseStatusCode)}
              </TableCell>
              <TableCell className="max-w-[150px] truncate font-mono text-xs">
                {attempt.msgId}
              </TableCell>
              <TableCell className="text-muted-foreground text-right text-sm">
                {formatTimestamp(attempt.timestamp)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function SecretField({
  subscriptionId,
  orgId,
}: {
  subscriptionId: string;
  orgId: string;
}) {
  const { getAccessTokenSilently } = useAuth0();
  const [isRevealed, setIsRevealed] = useState(false);
  const [secret, setSecret] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  const handleReveal = async () => {
    if (isRevealed) {
      setIsRevealed(false);
      return;
    }

    if (secret) {
      setIsRevealed(true);
      return;
    }

    setIsLoading(true);
    try {
      const token = await getAccessTokenSilently();
      const result = await fetchSubscriptionSecret(token, orgId, subscriptionId);
      setSecret(result.key);
      setIsRevealed(true);
    } catch (error) {
      console.error("Failed to fetch secret:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!secret) return;
    try {
      await navigator.clipboard.writeText(secret);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (error) {
      console.error("Failed to copy secret:", error);
    }
  };

  return (
    <div className="space-y-2">
      <Label>Signing Secret</Label>
      <div className="flex items-center gap-2 overflow-hidden">
        <div className="bg-muted w-0 flex-1 overflow-hidden rounded-md border px-3 py-2">
          <span className="block truncate font-mono text-sm">
            {isRevealed && secret ? secret : "••••••••••••••••••••••••••••••••"}
          </span>
        </div>
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="shrink-0"
          onClick={handleCopy}
          disabled={!secret}
          title="Copy to clipboard"
        >
          {isCopied ? (
            <Check className="size-4 text-green-500" />
          ) : (
            <Copy className="size-4" />
          )}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="shrink-0"
          onClick={handleReveal}
          disabled={isLoading}
          title={isRevealed ? "Hide secret" : "Reveal secret"}
        >
          {isLoading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : isRevealed ? (
            <EyeOff className="size-4" />
          ) : (
            <Eye className="size-4" />
          )}
        </Button>
      </div>
      <p className="text-muted-foreground text-xs">
        Use this secret to verify webhook signatures.
      </p>
    </div>
  );
}

function EditSubscriptionModal({
  subscriptionId,
  open,
  onOpenChange,
  orgId,
}: {
  subscriptionId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgId: string;
}) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>([]);

  // Fetch subscription data with message attempts when modal opens
  const {
    data: subscriptionData,
    isLoading: isLoadingSubscription,
  } = useQuery({
    queryKey: queryKeys.events.subscription(orgId, subscriptionId ?? ""),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSubscription(token, orgId, subscriptionId!);
    },
    enabled: open && !!subscriptionId,
  });

  const subscription = subscriptionData?.endpoint;
  const messageAttempts = subscriptionData?.message_attempts ?? [];

  // Sync state when subscription data is fetched
  useEffect(() => {
    if (subscription) {
      setUrl(subscription.url);
      setSelectedEventTypes(subscription.channels ?? []);
    }
  }, [subscription]);

  const handleOpenChange = (newOpen: boolean) => {
    onOpenChange(newOpen);
  };

  const updateMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return updateSubscription(token, orgId, subscriptionId!, {
        url,
        event_types: selectedEventTypes,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.events.subscriptions(orgId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.events.subscription(orgId, subscriptionId!),
      });
      onOpenChange(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return deleteSubscription(token, orgId, subscriptionId!);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.events.subscriptions(orgId),
      });
      onOpenChange(false);
    },
  });

  const handleUpdate = () => {
    updateMutation.mutate();
  };

  const handleDelete = () => {
    deleteMutation.mutate();
  };

  if (!subscriptionId) return null;

  const isValid = url && selectedEventTypes.length > 0;
  const isPending = updateMutation.isPending || deleteMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit Webhook</DialogTitle>
        </DialogHeader>
        {isLoadingSubscription ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="text-muted-foreground size-6 animate-spin" />
          </div>
        ) : (
          <>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="edit-webhook-url">Webhook URL</Label>
                <Input
                  id="edit-webhook-url"
                  type="url"
                  placeholder="https://example.com/webhook"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
                <p className="text-muted-foreground text-xs">
                  The URL that will receive webhook events via POST requests.
                </p>
              </div>
              <div className="space-y-2">
                <Label>Event Types</Label>
                <EventTypeSelector
                  selectedEventTypes={selectedEventTypes}
                  onSelectionChange={setSelectedEventTypes}
                />
                <p className="text-muted-foreground text-xs">
                  Select at least one event type to receive.
                </p>
              </div>
              <SecretField subscriptionId={subscriptionId!} orgId={orgId} />
              <div className="space-y-2">
                <Label>Delivery Attempts</Label>
                <MessageAttemptsTable attempts={messageAttempts} />
              </div>
            </div>
            <DialogFooter className="flex-row justify-between sm:justify-between">
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={isPending}
              >
                {deleteMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  "Delete"
                )}
              </Button>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => onOpenChange(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleUpdate}
                  disabled={!isValid || isPending}
                >
                  {updateMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      Updating...
                    </>
                  ) : (
                    "Update"
                  )}
                </Button>
              </div>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function SubscriptionsList({
  subscriptions,
  onCreateClick,
  onSubscriptionClick,
}: {
  subscriptions: Subscription[];
  onCreateClick: () => void;
  onSubscriptionClick: (subscription: Subscription) => void;
}) {
  if (subscriptions.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Subscriptions</CardTitle>
          <CardAction>
            <Button size="sm" onClick={onCreateClick}>
              <Plus className="mr-2 size-4" />
              Create Webhook
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">
            No subscriptions configured yet.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Subscriptions</CardTitle>
        <CardAction>
          <Button size="sm" onClick={onCreateClick}>
            <Plus className="mr-2 size-4" />
            Create Webhook
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="p-0">
        <div className="max-h-[300px] overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>URL</TableHead>
                <TableHead>Channels</TableHead>
                <TableHead className="text-right">Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {subscriptions.map((subscription) => (
                <TableRow
                  key={subscription.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => onSubscriptionClick(subscription)}
                >
                  <TableCell className="max-w-[300px] truncate font-mono text-sm">
                    {subscription.url}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {subscription.channels?.slice().sort().join(", ") || "All channels"}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-right text-sm">
                    {formatTimestamp(subscription.createdAt)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

function MessagesFilterModal({
  open,
  onOpenChange,
  selectedEventTypes,
  onApply,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedEventTypes: string[];
  onApply: (eventTypes: string[]) => void;
}) {
  const [localSelectedEventTypes, setLocalSelectedEventTypes] =
    useState<string[]>(selectedEventTypes);

  useEffect(() => {
    if (open) {
      setLocalSelectedEventTypes(selectedEventTypes);
    }
  }, [open, selectedEventTypes]);

  const handleApply = () => {
    onApply(localSelectedEventTypes);
    onOpenChange(false);
  };

  const handleClear = () => {
    setLocalSelectedEventTypes([]);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Filter Event Messages</DialogTitle>
        </DialogHeader>
        <div className="py-4">
          <EventTypeSelector
            selectedEventTypes={localSelectedEventTypes}
            onSelectionChange={setLocalSelectedEventTypes}
          />
          <p className="text-muted-foreground mt-2 text-xs">
            Select event types to filter. Leave empty to show all events.
          </p>
        </div>
        <DialogFooter className="flex-row justify-between sm:justify-between">
          <Button variant="outline" onClick={handleClear}>
            Clear
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleApply}>Apply</Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MessagesList({
  messages,
  onEventClick,
  filterEventTypes,
  onFilterClick,
  isLoading,
}: {
  messages: EventMessage[];
  onEventClick: (event: EventMessage) => void;
  filterEventTypes: string[];
  onFilterClick: () => void;
  isLoading?: boolean;
}) {
  const hasFilter = filterEventTypes.length > 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Event Messages</CardTitle>
        <CardAction>
          <Button
            size="sm"
            variant={hasFilter ? "default" : "outline"}
            onClick={onFilterClick}
          >
            <Filter className="mr-2 size-4" />
            Filter{hasFilter && ` (${filterEventTypes.length})`}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="text-muted-foreground size-6 animate-spin" />
          </div>
        ) : messages.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-muted-foreground text-sm">
              {hasFilter ? "No messages match the filter." : "No messages yet."}
            </p>
          </div>
        ) : (
          <div className="max-h-[500px] overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Event Type</TableHead>
                  <TableHead className="text-right">Timestamp</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {messages.map((message) => (
                  <TableRow
                    key={message.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => onEventClick(message)}
                  >
                    <TableCell className="font-mono text-sm">
                      {message.eventType}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-right text-sm">
                      {formatTimestamp(message.timestamp)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function WebhooksPage() {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const orgId = organization?.id ?? "";

  const [selectedEvent, setSelectedEvent] = useState<EventMessage | null>(null);
  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<
    string | null
  >(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [filterEventTypes, setFilterEventTypes] = useState<string[]>([]);
  const [filterModalOpen, setFilterModalOpen] = useState(false);

  const {
    data: subscriptions = [],
    isLoading: isLoadingSubscriptions,
  } = useQuery({
    queryKey: queryKeys.events.subscriptions(orgId),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSubscriptions(token, orgId);
    },
    enabled: !!orgId,
  });

  const {
    data: messages = [],
    isLoading: isLoadingMessages,
    error,
  } = useQuery({
    queryKey: queryKeys.events.messages(orgId, filterEventTypes),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchEventMessages(
        token,
        orgId,
        filterEventTypes.length > 0 ? filterEventTypes : undefined
      );
    },
    enabled: !!orgId,
  });

  const isLoading = isLoadingSubscriptions;

  usePageHeader({
    title: "Webhooks",
    description: "Receive real-time event notifications",
  });

  useRightSidebarContent({
    docs: <WebhooksDocs />,
    code: <WebhooksCode />,
    help: <WebhooksHelp />,
  });

  const handleEventClick = (event: EventMessage) => {
    setSelectedEvent(event);
    setEventModalOpen(true);
  };

  const handleCreateClick = () => {
    setCreateModalOpen(true);
  };

  const handleSubscriptionClick = (subscription: Subscription) => {
    setSelectedSubscriptionId(subscription.id);
    setEditModalOpen(true);
  };

  const handleFilterClick = () => {
    setFilterModalOpen(true);
  };

  const handleFilterApply = (eventTypes: string[]) => {
    setFilterEventTypes(eventTypes);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-6">
        <Loader2 className="text-muted-foreground size-6 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-destructive text-sm">
          Failed to load messages: {error.message}
        </p>
      </div>
    );
  }

  if (subscriptions.length === 0 && messages.length === 0) {
    return (
      <div className="p-6">
        <EmptyState
          icon={<Webhook />}
          title="Add your first webhook"
          description="Get notified when sync jobs complete, fail, or when new data is available."
        >
          <Button variant="outline" onClick={handleCreateClick}>
            <Plus className="mr-2 size-4" />
            Create Webhook
          </Button>
        </EmptyState>
        <CreateWebhookModal
          open={createModalOpen}
          onOpenChange={setCreateModalOpen}
          orgId={orgId}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <SubscriptionsList
        subscriptions={subscriptions}
        onCreateClick={handleCreateClick}
        onSubscriptionClick={handleSubscriptionClick}
      />
      <MessagesList
        messages={messages}
        onEventClick={handleEventClick}
        filterEventTypes={filterEventTypes}
        onFilterClick={handleFilterClick}
        isLoading={isLoadingMessages}
      />
      <EventDetailModal
        event={selectedEvent}
        open={eventModalOpen}
        onOpenChange={setEventModalOpen}
      />
      <CreateWebhookModal
        open={createModalOpen}
        onOpenChange={setCreateModalOpen}
        orgId={orgId}
      />
      <EditSubscriptionModal
        subscriptionId={selectedSubscriptionId}
        open={editModalOpen}
        onOpenChange={setEditModalOpen}
        orgId={orgId}
      />
      <MessagesFilterModal
        open={filterModalOpen}
        onOpenChange={setFilterModalOpen}
        selectedEventTypes={filterEventTypes}
        onApply={handleFilterApply}
      />
    </div>
  );
}
