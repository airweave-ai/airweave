import { Monitor, Smartphone, Globe } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Bowser from "bowser";
import { formatRelativeTime } from "@/utils/dateTime";
import type { UserSession } from "@/types";

interface SessionCardProps {
  session: UserSession;
  onTerminate: (sessionId: string) => void;
  isTerminating: boolean;
}

function parseUserAgent(ua?: string) {
  if (!ua) return { device: "Unknown device", browser: "Unknown browser" };
  const parsed = Bowser.parse(ua);
  const browserStr = [parsed.browser.name, parsed.browser.version?.split(".")[0]]
    .filter(Boolean)
    .join(" ");
  const osStr = [parsed.os.name, parsed.os.version].filter(Boolean).join(" ");
  const deviceType = parsed.platform.type || "desktop";

  return {
    device: osStr || "Unknown OS",
    browser: browserStr || "Unknown browser",
    deviceType,
  };
}

export function SessionCard({ session, onTerminate, isTerminating }: SessionCardProps) {
  const { device, browser, deviceType } = parseUserAgent(session.user_agent);
  const DeviceIcon = deviceType === "mobile" ? Smartphone : Monitor;

  return (
    <div className="flex items-center justify-between rounded-lg border p-4">
      <div className="flex items-center gap-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
          <DeviceIcon className="h-5 w-5 text-muted-foreground" />
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{browser} on {device}</span>
            {session.is_current && (
              <Badge variant="secondary" className="text-xs">Current</Badge>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {session.ip_address && (
              <span className="flex items-center gap-1">
                <Globe className="h-3 w-3" />
                {session.ip_address}
              </span>
            )}
            <span>Active {formatRelativeTime(session.last_active_at)}</span>
          </div>
        </div>
      </div>
      {!session.is_current && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => onTerminate(session.id)}
          disabled={isTerminating}
        >
          {isTerminating ? "Signing out..." : "Sign out"}
        </Button>
      )}
    </div>
  );
}
