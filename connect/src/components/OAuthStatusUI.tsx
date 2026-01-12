import { ExternalLink, Loader2 } from "lucide-react";
import { Button } from "./Button";

type OAuthStatus = "idle" | "creating" | "waiting" | "popup_blocked" | "error";

interface OAuthStatusUIProps {
  status: OAuthStatus;
  error: string | null;
  blockedAuthUrl: string | null;
  sourceName: string;
  onConnect: () => void;
  onRetryPopup: () => void;
  onManualLinkClick: () => void;
}

export function OAuthStatusUI({
  status,
  error,
  blockedAuthUrl,
  sourceName,
  onConnect,
  onRetryPopup,
  onManualLinkClick,
}: OAuthStatusUIProps) {
  return (
    <>
      {error && (
        <div
          className="mb-3 p-3 rounded-md text-sm"
          style={{
            backgroundColor:
              "color-mix(in srgb, var(--connect-error) 10%, transparent)",
            color: "var(--connect-error)",
          }}
        >
          {error}
        </div>
      )}

      {status === "waiting" && (
        <div
          className="p-4 rounded-md text-sm text-center"
          style={{
            backgroundColor: "var(--connect-surface)",
            border: "1px solid var(--connect-border)",
          }}
        >
          <Loader2
            className="w-5 h-5 animate-spin mx-auto mb-2"
            style={{ color: "var(--connect-primary)" }}
          />
          <p style={{ color: "var(--connect-text)" }}>
            Waiting for authorization...
          </p>
          <p
            className="text-xs mt-1"
            style={{ color: "var(--connect-text-muted)" }}
          >
            Complete the sign-in in the popup window
          </p>
        </div>
      )}

      {status === "popup_blocked" && blockedAuthUrl && (
        <div
          className="p-4 rounded-md text-sm"
          style={{
            backgroundColor:
              "color-mix(in srgb, var(--connect-warning, #f59e0b) 10%, transparent)",
            border:
              "1px solid color-mix(in srgb, var(--connect-warning, #f59e0b) 30%, transparent)",
          }}
        >
          <p
            className="font-medium mb-2"
            style={{ color: "var(--connect-text)" }}
          >
            Popup was blocked
          </p>
          <p
            className="text-xs mb-3"
            style={{ color: "var(--connect-text-muted)" }}
          >
            Your browser blocked the authentication popup. You can try again or
            open the link manually.
          </p>
          <div className="flex flex-col gap-2">
            <Button
              type="button"
              onClick={onRetryPopup}
              className="w-full justify-center"
              variant="secondary"
            >
              <ExternalLink className="w-4 h-4" />
              Try again
            </Button>
            <a
              href={blockedAuthUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={onManualLinkClick}
              className="w-full px-4 py-2 text-sm rounded-md text-center transition-colors"
              style={{
                color: "var(--connect-primary)",
                border: "1px solid var(--connect-border)",
                backgroundColor: "var(--connect-surface)",
              }}
            >
              Open link manually
            </a>
          </div>
        </div>
      )}

      {status !== "waiting" && status !== "popup_blocked" && (
        <Button
          type="button"
          onClick={onConnect}
          disabled={status === "creating"}
          className="w-full justify-center"
          variant="secondary"
        >
          {status === "creating" ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Connecting...
            </>
          ) : (
            <>
              <ExternalLink className="w-4 h-4" />
              Connect with {sourceName}
            </>
          )}
        </Button>
      )}
    </>
  );
}
