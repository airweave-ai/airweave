import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// Badge is used in EventTypeBadge below

/**
 * Format timestamp to readable string
 */
export function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/**
 * Format time only (HH:MM:SS)
 */
export function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

/**
 * Format full date with time
 */
export function formatFullDate(timestamp: string): string {
  const date = new Date(timestamp);
  return new Intl.DateTimeFormat("en-US", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

/**
 * Format relative time (e.g., "2m ago", "1h ago")
 */
export function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return formatTimestamp(timestamp);
}

/**
 * Status Badge Component - minimal pill style
 */
export function StatusBadge({ statusCode }: { statusCode: number | null }) {
  if (!statusCode) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground">
        Pending
      </span>
    );
  }
  if (statusCode >= 200 && statusCode < 300) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
        {statusCode}
      </span>
    );
  } else if (statusCode >= 400 && statusCode < 500) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400">
        {statusCode}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-500/10 text-red-600 dark:text-red-400">
      {statusCode}
    </span>
  );
}

/**
 * Event Type Badge Component
 */
export function EventTypeBadge({ eventType }: { eventType: string }) {
  const getVariant = () => {
    if (eventType.includes("completed"))
      return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800";
    if (eventType.includes("failed"))
      return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 border-red-200 dark:border-red-800";
    if (eventType.includes("running"))
      return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 border-blue-200 dark:border-blue-800";
    if (eventType.includes("pending"))
      return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border-amber-200 dark:border-amber-800";
    if (eventType.includes("cancelled"))
      return "bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400 border-gray-200 dark:border-gray-800";
    return "bg-muted text-muted-foreground";
  };

  return (
    <Badge variant="outline" className={cn("font-mono text-xs", getVariant())}>
      {eventType}
    </Badge>
  );
}

/**
 * Get summary from message payload
 */
export function getMessageSummary(payload: Record<string, unknown>): string {
  // Try to build a meaningful summary from the payload
  const collectionName = payload.collection_name as string | undefined;
  const sourceType = payload.source_type as string | undefined;
  const status = payload.status as string | undefined;

  if (collectionName && sourceType) {
    return `${sourceType} → ${collectionName}`;
  }
  if (collectionName) {
    return collectionName;
  }
  if (status) {
    return `Sync ${status}`;
  }
  return "";
}

/**
 * Event types configuration
 */
export const EVENT_TYPES_CONFIG = {
  sync: {
    label: "Sync Events",
    events: [
      { id: "sync.pending", label: "Pending" },
      { id: "sync.running", label: "Running" },
      { id: "sync.completed", label: "Completed" },
      { id: "sync.failed", label: "Failed" },
      { id: "sync.cancelled", label: "Cancelled" },
    ],
  },
} as const;

export type EventTypeGroup = keyof typeof EVENT_TYPES_CONFIG;

/**
 * Get event type label from id
 */
export function getEventTypeLabel(eventId: string): string {
  for (const group of Object.values(EVENT_TYPES_CONFIG)) {
    const event = group.events.find((e) => e.id === eventId);
    if (event) return event.label;
  }
  return eventId;
}
