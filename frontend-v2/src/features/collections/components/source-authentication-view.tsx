/**
 * SourceAuthenticationView - OAuth flow UI for source connections
 */

import { ExternalLink, Loader2, RefreshCw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { getAppIconUrl } from "../utils/helpers";

interface SourceAuthenticationViewProps {
  sourceName: string;
  sourceShortName: string;
  authenticationUrl?: string;
  onRefreshUrl?: () => void;
  isRefreshing?: boolean;
  onDelete?: () => void;
  className?: string;
}

export function SourceAuthenticationView({
  sourceName,
  sourceShortName,
  authenticationUrl,
  onRefreshUrl,
  isRefreshing,
  onDelete,
  className,
}: SourceAuthenticationViewProps) {
  const iconUrl = getAppIconUrl(sourceShortName);

  return (
    <div
      className={cn(
        "rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-6",
        className
      )}
    >
      <div className="flex flex-col items-center text-center">
        {/* Source Icon */}
        <div className="bg-background mb-4 flex size-16 items-center justify-center overflow-hidden rounded-lg border p-2">
          <img
            src={iconUrl}
            alt={sourceName}
            className="size-full object-contain"
          />
        </div>

        <h3 className="mb-2 text-lg font-semibold">Connect to {sourceName}</h3>
        <p className="text-muted-foreground mb-6 max-w-md text-sm">
          This source requires authentication. Click the button below to
          authorize access to your {sourceName} data.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3">
          {authenticationUrl ? (
            <Button asChild>
              <a
                href={authenticationUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="mr-2 size-4" />
                Authenticate with {sourceName}
              </a>
            </Button>
          ) : (
            <Button disabled>
              <Loader2 className="mr-2 size-4 animate-spin" />
              Generating auth URL...
            </Button>
          )}

          {onRefreshUrl && (
            <Button
              variant="outline"
              onClick={onRefreshUrl}
              disabled={isRefreshing}
            >
              {isRefreshing ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 size-4" />
              )}
              Refresh URL
            </Button>
          )}

          {onDelete && (
            <Button
              variant="outline"
              onClick={onDelete}
              className="text-destructive hover:bg-destructive/10 hover:text-destructive"
            >
              <Trash2 className="mr-2 size-4" />
              Remove
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
