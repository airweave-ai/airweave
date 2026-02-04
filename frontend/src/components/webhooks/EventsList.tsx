import { Input } from "@/components/ui/input";
import { Loader2, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatTime, getEventSummary } from "./shared";
import type { Message } from "@/hooks/use-webhooks";

interface EventsListProps {
  messages: Message[];
  selectedId: string | null;
  onSelect: (message: Message) => void;
  isLoading: boolean;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export function EventsList({
  messages,
  selectedId,
  onSelect,
  isLoading,
  searchQuery,
  onSearchChange,
}: EventsListProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="p-2 border-b">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/60" />
          <Input
            type="text"
            placeholder="Search events..."
            className="pl-8 h-8 text-xs bg-transparent border-0 focus-visible:ring-0 placeholder:text-muted-foreground/50"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="size-4 animate-spin text-muted-foreground/50" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <p className="text-xs text-muted-foreground/60">
              {searchQuery ? "No results" : "No events"}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border/40">
            {messages.map((message) => {
              const isSelected = selectedId === message.id;
              const summary = getEventSummary(message.payload);

              return (
                <div
                  key={message.id}
                  onClick={() => onSelect(message)}
                  className={cn(
                    "flex items-center justify-between px-3 py-2 cursor-pointer transition-colors",
                    isSelected
                      ? "bg-muted/60"
                      : "hover:bg-muted/30"
                  )}
                >
                  <div className="min-w-0 mr-3">
                    <p className="font-mono text-[13px] truncate">
                      {message.event_type}
                    </p>
                    {summary && (
                      <p className="text-[11px] text-muted-foreground/70 truncate">
                        {summary}
                      </p>
                    )}
                  </div>
                  <span className="text-[11px] text-muted-foreground/50 tabular-nums shrink-0">
                    {formatTime(message.timestamp)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
