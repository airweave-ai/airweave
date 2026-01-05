/**
 * ConnectionPreview - Visual indicator showing connection between Airweave and a provider
 */

import { useIsDark } from "@/hooks/use-is-dark";
import { cn } from "@/lib/utils";

import { getAuthProviderIconUrl } from "../utils/helpers";

interface ConnectionPreviewProps {
  providerShortName: string;
  providerName: string;
  status?: "pending" | "connected" | "error";
}

export function ConnectionPreview({
  providerShortName,
  providerName,
  status = "pending",
}: ConnectionPreviewProps) {
  const isDark = useIsDark();

  const statusText = {
    pending: "Waiting for connection...",
    connected: "Connected",
    error: "Connection failed",
  }[status];

  return (
    <div className="flex justify-center py-4">
      <div className="flex items-center gap-6">
        {/* Airweave Logo */}
        <div
          className={cn(
            "flex h-14 w-14 items-center justify-center rounded-xl p-2.5",
            "ring-muted-foreground/20 shadow-lg ring-2",
            "bg-card"
          )}
        >
          <img
            src={
              isDark
                ? "/airweave-logo-svg-white-darkbg.svg"
                : "/airweave-logo-svg-lightbg-blacklogo.svg"
            }
            alt="Airweave"
            className="h-full w-full object-contain"
          />
        </div>

        {/* Status text */}
        <span className="text-muted-foreground text-sm">{statusText}</span>

        {/* Auth Provider Logo */}
        <div
          className={cn(
            "flex h-14 w-14 items-center justify-center rounded-xl p-2.5",
            "ring-muted-foreground/20 shadow-lg ring-2",
            "bg-card"
          )}
        >
          <img
            src={getAuthProviderIconUrl(
              providerShortName,
              isDark ? "dark" : "light"
            )}
            alt={providerName}
            className="h-full w-full object-contain"
          />
        </div>
      </div>
    </div>
  );
}

