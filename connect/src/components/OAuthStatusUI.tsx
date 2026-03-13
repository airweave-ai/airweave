import { ExternalLink, Loader2 } from "lucide-react";
import { useTheme } from "../lib/theme";
import type { OAuthFlowStatus } from "../lib/types";
import { Button } from "./Button";

interface OAuthStatusUIProps {
  status: OAuthFlowStatus;
  error: string | null;
  blockedAuthUrl: string | null;
  onRetryPopup: () => void;
  onManualLinkClick: () => void;
}

export function OAuthStatusUI({
  status,
  error,
  blockedAuthUrl,
  onRetryPopup,
  onManualLinkClick,
}: OAuthStatusUIProps) {
  const { labels } = useTheme();
  return (
    <>
      {error && (
        <div
          className="mb-3 p-3 rounded-md text-sm"
          role="alert"
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
          role="status"
          aria-live="polite"
          style={{
            backgroundColor: "var(--connect-surface)",
            border: "1px solid var(--connect-border)",
          }}
        >
          <Loader2
            className="w-5 h-5 animate-spin mx-auto mb-2"
            aria-hidden="true"
            style={{ color: "var(--connect-primary)" }}
          />
          <p style={{ color: "var(--connect-text)" }}>{labels.oauthWaiting}</p>
          <p
            className="text-xs mt-1"
            style={{ color: "var(--connect-text-muted)" }}
          >
            {labels.oauthWaitingDescription}
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
            {labels.oauthPopupBlocked}
          </p>
          <p
            className="text-xs mb-3"
            style={{ color: "var(--connect-text-muted)" }}
          >
            {labels.oauthPopupBlockedDescription}
          </p>
          <div className="flex flex-col gap-2">
            <Button
              type="button"
              onClick={onRetryPopup}
              className="w-full justify-center"
              variant="secondary"
            >
              <ExternalLink className="w-4 h-4" />
              {labels.buttonTryAgain}
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
              {labels.buttonOpenLinkManually}
            </a>
          </div>
        </div>
      )}
    </>
  );
}
