import { Eye, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useIsDark } from "@/hooks/use-is-dark";
import { cn } from "@/lib/utils";

import { getAppIconUrl, getCollectionStatusDisplay } from "../utils/helpers";

interface SourceConnection {
  id: string;
  name: string;
  short_name: string;
}

interface CollectionCardProps {
  id: string;
  name: string;
  readableId: string;
  status?: string;
  sourceConnections?: SourceConnection[];
  onClick?: () => void;
  className?: string;
}

export function CollectionCard({
  name,
  readableId,
  status = "ACTIVE",
  sourceConnections = [],
  onClick,
  className,
}: CollectionCardProps) {
  const isDark = useIsDark();
  const statusDisplay = getCollectionStatusDisplay(status);

  return (
    <div
      className={cn(
        "group relative flex h-full min-w-[240px] cursor-pointer flex-col overflow-hidden rounded-xl border transition-colors",
        "border-slate-200 bg-white hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700",
        className
      )}
      onClick={onClick}
    >
      {/* Card Content */}
      <div className="flex flex-1 flex-col p-4">
        <div className="mb-2 flex items-start justify-between">
          <h3 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-white">
            {name}
          </h3>
        </div>
        <p className="mb-3 truncate text-sm text-slate-500 dark:text-slate-400">
          {readableId}.airweave.ai
        </p>

        {/* Status badge */}
        <Badge
          variant={
            statusDisplay.variant === "success"
              ? "default"
              : statusDisplay.variant === "warning"
                ? "secondary"
                : statusDisplay.variant === "destructive"
                  ? "destructive"
                  : "outline"
          }
          className={cn(
            "w-fit",
            statusDisplay.variant === "success" &&
              "border-transparent bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
            statusDisplay.variant === "warning" &&
              "border-transparent bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
          )}
        >
          {statusDisplay.label}
        </Badge>
      </div>

      {/* Card Footer */}
      <div className="flex items-center justify-between border-t border-slate-100 p-2 dark:border-slate-800">
        {/* View & Edit Button */}
        <Button
          variant="ghost"
          size="sm"
          className="rounded-lg text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white"
          onClick={(e) => {
            e.stopPropagation();
            onClick?.();
          }}
        >
          <Eye className="mr-1.5 h-4 w-4" />
          View & edit
        </Button>

        {/* Source connection icons */}
        <SourceConnectionIcons
          connections={sourceConnections}
          isDark={isDark}
        />
      </div>
    </div>
  );
}

interface SourceConnectionIconsProps {
  connections: SourceConnection[];
  isDark: boolean;
}

function renderFallbackIcon(target: HTMLImageElement, fallbackContent: string) {
  target.style.display = "none";
  const parent = target.parentElement;
  if (parent) {
    parent.innerHTML = `<div class="flex h-full w-full items-center justify-center">${fallbackContent}</div>`;
  }
}

function SourceConnectionIcons({
  connections,
  isDark,
}: SourceConnectionIconsProps) {
  if (connections.length === 0) {
    return (
      <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-slate-100 p-2 dark:border-slate-700 dark:bg-slate-800">
        <Plus className="h-full w-full text-slate-400" />
      </div>
    );
  }

  if (connections.length === 1) {
    return (
      <div className="flex items-center justify-center">
        <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white p-1 dark:border-slate-700 dark:bg-slate-800">
          <img
            src={getAppIconUrl(
              connections[0].short_name,
              isDark ? "dark" : "light"
            )}
            alt={connections[0].name}
            className="h-full w-full object-contain"
            onError={(e) =>
              renderFallbackIcon(
                e.currentTarget,
                `<span class="text-muted-foreground"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg></span>`
              )
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center">
      <div className="flex -space-x-2">
        {connections.slice(0, 2).map((connection, index) => (
          <div
            key={connection.id}
            className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white p-1.5 dark:border-slate-700 dark:bg-slate-800"
            style={{ zIndex: 2 - index }}
          >
            <img
              src={getAppIconUrl(
                connection.short_name,
                isDark ? "dark" : "light"
              )}
              alt={connection.name}
              className="h-full w-full object-contain"
              onError={(e) =>
                renderFallbackIcon(
                  e.currentTarget,
                  `<span class="font-semibold text-xs text-muted-foreground">${connection.short_name.substring(0, 2).toUpperCase()}</span>`
                )
              }
            />
          </div>
        ))}
      </div>
      {connections.length > 2 && (
        <div className="ml-1 text-xs font-medium text-slate-500 dark:text-slate-400">
          +{connections.length - 2}
        </div>
      )}
    </div>
  );
}
