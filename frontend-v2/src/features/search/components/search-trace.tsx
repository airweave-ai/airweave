/**
 * SearchTrace - Real-time display of search operation events
 *
 * Shows the search pipeline progress including:
 * - Query expansion
 * - Filter interpretation
 * - Retrieval
 * - Reranking
 * - Completion generation
 */

import { Check, ChevronDown, ChevronRight, Copy, Loader2 } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { useAutoScroll } from "@/hooks/use-auto-scroll";
import { cn } from "@/lib/utils";

import type { SearchEvent } from "../types";

interface SearchTraceProps {
  events: SearchEvent[];
  isSearching?: boolean;
  className?: string;
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  query_expansion_started: "Query Expansion",
  query_expansion_done: "Query Expansion",
  filter_interpretation_started: "Filter Interpretation",
  filter_interpretation_done: "Filter Interpretation",
  retrieval_started: "Retrieval",
  retrieval_done: "Retrieval",
  reranking_started: "Reranking",
  reranking_done: "Reranking",
  completion_started: "Generating Answer",
  completion_chunk: "Generating Answer",
  completion_done: "Answer Complete",
  results: "Results",
  done: "Complete",
  error: "Error",
};

interface EventGroup {
  id: string;
  label: string;
  events: SearchEvent[];
  status: "pending" | "in_progress" | "completed" | "error";
  duration?: number;
  output?: unknown;
}

function groupEvents(events: SearchEvent[]): EventGroup[] {
  const groups: EventGroup[] = [];
  const groupMap = new Map<string, EventGroup>();

  for (const event of events) {
    const eventType: string = event.type;

    let groupKey = eventType;
    let status: EventGroup["status"] = "completed";

    if (eventType.endsWith("_started")) {
      groupKey = eventType.replace("_started", "");
      status = "in_progress";
    } else if (eventType.endsWith("_done")) {
      groupKey = eventType.replace("_done", "");
      status = "completed";
    } else if (eventType === "completion_chunk") {
      groupKey = "completion";
      status = "in_progress";
    } else if (eventType === "error") {
      status = "error";
    }

    const label = EVENT_TYPE_LABELS[eventType] || eventType;

    let group = groupMap.get(groupKey);
    if (!group) {
      group = {
        id: groupKey,
        label,
        events: [],
        status: "pending",
      };
      groupMap.set(groupKey, group);
      groups.push(group);
    }

    group.events.push(event);
    group.status = status;
    group.label = label;

    const eventData = event as unknown as Record<string, unknown>;
    if (eventData.expanded_queries) {
      group.output = { expanded_queries: eventData.expanded_queries };
    }
    if (eventData.interpreted_filter) {
      group.output = { interpreted_filter: eventData.interpreted_filter };
    }
    if (eventData.results) {
      group.output = { result_count: (eventData.results as unknown[]).length };
    }
    if (eventData.duration_ms) {
      group.duration = eventData.duration_ms as number;
    }
  }

  return groups;
}

function StatusIndicator({ status }: { status: EventGroup["status"] }) {
  switch (status) {
    case "pending":
      return <div className="size-2 rounded-full bg-slate-500" />;
    case "in_progress":
      return <Loader2 className="size-3 animate-spin text-blue-500" />;
    case "completed":
      return (
        <div className="flex size-4 items-center justify-center rounded-full bg-green-500/20">
          <Check className="size-2.5 text-green-500" />
        </div>
      );
    case "error":
      return <div className="size-2 rounded-full bg-red-500" />;
    default:
      return null;
  }
}

function EventGroupRow({
  group,
  isExpanded,
  onToggle,
}: {
  group: EventGroup;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const output = group.output as Record<string, unknown> | undefined;
  const hasOutput = output && Object.keys(output).length > 0;

  return (
    <div className="border-b border-slate-800 last:border-b-0">
      <button
        onClick={hasOutput ? onToggle : undefined}
        className={cn(
          "flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors",
          hasOutput && "cursor-pointer hover:bg-slate-800/50"
        )}
        disabled={!hasOutput}
      >
        <div className="w-4">
          {hasOutput &&
            (isExpanded ? (
              <ChevronDown className="size-3.5 text-slate-400" />
            ) : (
              <ChevronRight className="size-3.5 text-slate-400" />
            ))}
        </div>

        <StatusIndicator status={group.status} />

        <span
          className={cn(
            "flex-1 text-sm",
            group.status === "error" ? "text-red-400" : "text-slate-200"
          )}
        >
          {group.label}
        </span>

        {group.duration !== undefined && (
          <span className="text-xs text-slate-500">{group.duration}ms</span>
        )}
      </button>

      {isExpanded && hasOutput && (
        <div className="border-t border-slate-800 bg-slate-950 px-4 py-3">
          <pre className="overflow-x-auto text-xs text-slate-400">
            {JSON.stringify(output, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export function SearchTrace({
  events,
  isSearching = false,
  className,
}: SearchTraceProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);

  const scrollRef = useAutoScroll([events], { enabled: isSearching });
  const eventGroups = useMemo(() => groupEvents(events), [events]);

  const toggleGroup = useCallback((groupId: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) {
        next.delete(groupId);
      } else {
        next.add(groupId);
      }
      return next;
    });
  }, []);

  const handleCopyTrace = useCallback(async () => {
    const traceData = {
      timestamp: new Date().toISOString(),
      events: events,
    };
    await navigator.clipboard.writeText(JSON.stringify(traceData, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [events]);

  if (events.length === 0 && !isSearching) {
    return null;
  }

  return (
    <div className={cn("overflow-hidden", className)}>
      <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-200">
            Search Trace
          </span>
          {isSearching && (
            <Loader2 className="size-3 animate-spin text-blue-500" />
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopyTrace}
          className="size-7 p-0 text-slate-400 hover:text-slate-200"
          title="Copy trace"
        >
          {copied ? (
            <Check className="size-3.5 text-green-500" />
          ) : (
            <Copy className="size-3.5" />
          )}
        </Button>
      </div>

      <div
        ref={scrollRef}
        className="max-h-[400px] overflow-y-auto bg-slate-900/50"
      >
        {eventGroups.map((group) => (
          <EventGroupRow
            key={group.id}
            group={group}
            isExpanded={expandedGroups.has(group.id)}
            onToggle={() => toggleGroup(group.id)}
          />
        ))}

        {isSearching && events.length === 0 && (
          <div className="flex items-center gap-3 px-4 py-3">
            <Loader2 className="size-4 animate-spin text-blue-500" />
            <span className="text-sm text-slate-400">Starting search...</span>
          </div>
        )}
      </div>
    </div>
  );
}
