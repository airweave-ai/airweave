import { createFileRoute } from "@tanstack/react-router";
import { Check, X } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import type { OAuthCallbackResult } from "../lib/types";

export const Route = createFileRoute("/oauth-callback")({
  component: OAuthCallback,
});

function parseOAuthResult(): {
  result: OAuthCallbackResult;
  hasOpener: boolean;
} {
  if (typeof window === "undefined") {
    return {
      result: { status: "error", error_message: "Server-side rendering" },
      hasOpener: false,
    };
  }

  const params = new URLSearchParams(window.location.search);
  const callbackStatus = params.get("status") as "success" | "error" | null;

  return {
    result: {
      status: callbackStatus ?? "error",
      source_connection_id: params.get("source_connection_id") ?? undefined,
      error_type: params.get("error_type") ?? undefined,
      error_message: params.get("error_message") ?? undefined,
    },
    hasOpener: !!window.opener,
  };
}

const containerStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  height: "100vh",
  fontFamily: "system-ui, -apple-system, sans-serif",
  textAlign: "center",
  padding: "20px",
  backgroundColor: "#f9fafb",
};

const iconContainerStyle = (success: boolean): React.CSSProperties => ({
  width: "48px",
  height: "48px",
  backgroundColor: success ? "#10b981" : "#ef4444",
  borderRadius: "50%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  marginBottom: "16px",
});

function OAuthCallback() {
  const { result, hasOpener } = useMemo(() => parseOAuthResult(), []);
  const hasNotified = useRef(false);

  const isSuccess = hasOpener && result.status === "success";

  const errorMessage = !hasOpener
    ? "Unable to complete authentication. Please close this window and try again."
    : result.status === "error"
      ? (result.error_message ?? "Authentication failed")
      : null;

  useEffect(() => {
    if (hasNotified.current || !window.opener) return;
    hasNotified.current = true;

    // Use same origin since popup is opened from Connect widget (same-origin)
    // This prevents other windows from intercepting the OAuth result
    window.opener.postMessage(
      { type: "OAUTH_COMPLETE", ...result },
      window.location.origin
    );
    setTimeout(() => window.close(), 1500);
  }, [result]);

  return (
    <div style={containerStyle}>
      <div style={iconContainerStyle(isSuccess)}>
        {isSuccess ? (
          <Check size={24} color="white" strokeWidth={3} />
        ) : (
          <X size={24} color="white" strokeWidth={3} />
        )}
      </div>
      <p style={{ color: "#374151", fontSize: "16px" }}>
        {isSuccess ? "Authentication successful!" : "Authentication failed"}
      </p>
      {errorMessage && (
        <p style={{ color: "#6b7280", fontSize: "14px", marginTop: "8px" }}>
          {errorMessage}
        </p>
      )}
      <p style={{ color: "#6b7280", fontSize: "14px", marginTop: "8px" }}>
        This window will close automatically.
      </p>
    </div>
  );
}
