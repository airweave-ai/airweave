import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ChevronRight, Copy, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge, formatFullDate, formatRelativeTime, formatTime } from "./shared";
import { useMessage, type Message, type MessageAttempt } from "@/hooks/use-webhooks";

/**
 * Syntax-highlighted JSON renderer
 */
function JsonSyntax({ data }: { data: unknown }) {
  const renderValue = (value: unknown, depth: number = 0): JSX.Element => {
    const indent = "  ".repeat(depth);
    const nextIndent = "  ".repeat(depth + 1);

    if (value === null) {
      return <span className="text-orange-600 dark:text-orange-500">null</span>;
    }

    if (typeof value === "boolean") {
      return (
        <span className="text-violet-600 dark:text-violet-400">
          {value.toString()}
        </span>
      );
    }

    if (typeof value === "number") {
      return (
        <span className="text-blue-600 dark:text-blue-400">{value}</span>
      );
    }

    if (typeof value === "string") {
      return (
        <span className="text-emerald-600 dark:text-emerald-500">
          "{value}"
        </span>
      );
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        return <span className="text-muted-foreground/60">[]</span>;
      }
      return (
        <>
          <span className="text-muted-foreground/60">[</span>
          {"\n"}
          {value.map((item, i) => (
            <span key={i}>
              {nextIndent}
              {renderValue(item, depth + 1)}
              {i < value.length - 1 && <span className="text-muted-foreground/40">,</span>}
              {"\n"}
            </span>
          ))}
          {indent}
          <span className="text-muted-foreground/60">]</span>
        </>
      );
    }

    if (typeof value === "object") {
      const entries = Object.entries(value as Record<string, unknown>);
      if (entries.length === 0) {
        return <span className="text-muted-foreground/60">{"{}"}</span>;
      }
      return (
        <>
          <span className="text-muted-foreground/60">{"{"}</span>
          {"\n"}
          {entries.map(([key, val], i) => (
            <span key={key}>
              {nextIndent}
              <span className="text-rose-600 dark:text-rose-400">"{key}"</span>
              <span className="text-muted-foreground/40">: </span>
              {renderValue(val, depth + 1)}
              {i < entries.length - 1 && <span className="text-muted-foreground/40">,</span>}
              {"\n"}
            </span>
          ))}
          {indent}
          <span className="text-muted-foreground/60">{"}"}</span>
        </>
      );
    }

    return <span>{String(value)}</span>;
  };

  return (
    <pre className="text-[11px] font-mono leading-relaxed whitespace-pre">
      {renderValue(data)}
    </pre>
  );
}

interface EventDetailProps {
  message: Message | null;
}

/**
 * Get status label for display
 */
function getStatusLabel(status: string): string {
  switch (status) {
    case "success": return "Success";
    case "pending": return "Pending";
    case "failed": return "Failed";
    default: return "Unknown";
  }
}

function DeliveryAttempts({
  messageId,
}: {
  messageId: string;
}) {
  // Fetch message with delivery attempts included
  const { data: message, isLoading } = useMessage(messageId, true);
  const attempts: MessageAttempt[] = message?.delivery_attempts ?? [];
  const [expandedAttempt, setExpandedAttempt] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="py-8 flex justify-center">
        <Loader2 className="size-4 animate-spin text-muted-foreground/40" />
      </div>
    );
  }

  if (attempts.length === 0) {
    return (
      <p className="text-xs text-muted-foreground/60 py-6 text-center">
        No delivery attempts
      </p>
    );
  }

  return (
    <div className="divide-y divide-border/30">
      {attempts.map((attempt) => {
        const isExpanded = expandedAttempt === attempt.id;
        const isSuccess = attempt.response_status_code >= 200 && attempt.response_status_code < 300;

        return (
          <div key={attempt.id}>
            <button
              onClick={() => setExpandedAttempt(isExpanded ? null : attempt.id)}
              className="w-full flex items-center gap-2 py-2.5 hover:bg-muted/30 transition-colors text-left group"
            >
              <ChevronRight
                className={cn(
                  "size-3 text-muted-foreground/40 transition-transform shrink-0",
                  isExpanded && "rotate-90"
                )}
              />
              <StatusBadge statusCode={attempt.response_status_code} />
              <span className="text-[12px] font-mono truncate flex-1 text-muted-foreground group-hover:text-foreground transition-colors">
                {attempt.endpoint_id}
              </span>
              <span
                className="text-[10px] text-muted-foreground/50 shrink-0"
                title={formatFullDate(attempt.timestamp)}
              >
                {formatRelativeTime(attempt.timestamp)}
              </span>
            </button>

            {isExpanded && (
              <div className="ml-5 mb-3 p-3 bg-muted/20 rounded-md border border-border/30">
                <div className="grid grid-cols-3 gap-4 text-[11px]">
                  <div>
                    <p className="text-muted-foreground/40 text-[10px] uppercase tracking-wide mb-0.5">Time</p>
                    <p className="font-mono text-muted-foreground">{formatTime(attempt.timestamp)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground/40 text-[10px] uppercase tracking-wide mb-0.5">Status</p>
                    <p className="text-muted-foreground">{getStatusLabel(attempt.status)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground/40 text-[10px] uppercase tracking-wide mb-0.5">Attempt</p>
                    <p className="font-mono text-muted-foreground truncate" title={attempt.id}>
                      {attempt.id.slice(0, 16)}
                    </p>
                  </div>
                </div>

                {attempt.response && (
                  <div className="mt-3 pt-3 border-t border-border/30">
                    <p className="text-muted-foreground/40 text-[10px] uppercase tracking-wide mb-1.5">Response</p>
                    <pre className="text-[11px] font-mono text-muted-foreground/80 bg-background/50 p-2.5 rounded border border-border/20 overflow-auto max-h-28">
                      {attempt.response}
                    </pre>
                  </div>
                )}

                {!attempt.response && !isSuccess && (
                  <div className="mt-3 pt-3 border-t border-border/30">
                    <p className="text-[11px] text-muted-foreground/40 italic">No response body</p>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function EventDetail({ message }: EventDetailProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(JSON.stringify(message?.payload, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (!message) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-xs text-muted-foreground/50">Select an event</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="p-4 space-y-5">
        {/* Header */}
        <div>
          <h2 className="font-mono text-[13px]">{message.event_type}</h2>
          <p className="text-[11px] text-muted-foreground/50 mt-0.5 font-mono">
            {message.id}
          </p>
        </div>

        {/* Metadata */}
        <div className="text-[11px]">
          <p className="text-muted-foreground/40">Created</p>
          <p className="text-muted-foreground/70">{formatFullDate(message.timestamp)}</p>
        </div>

        {/* Deliveries */}
        <div>
          <p className="text-[11px] text-muted-foreground/40 mb-1.5">Webhook deliveries</p>
          <DeliveryAttempts messageId={message.id} />
        </div>

        {/* Payload */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-[11px] text-muted-foreground/40">Payload</p>
            <Button
              variant="ghost"
              size="sm"
              className="h-5 px-1.5 text-[10px] text-muted-foreground/40 hover:text-muted-foreground"
              onClick={handleCopy}
            >
              <Copy className="size-2.5 mr-1" />
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <div className="bg-muted/40 rounded-md p-3">
            <JsonSyntax data={message.payload} />
          </div>
        </div>
      </div>
    </div>
  );
}
