import { AlertCircle, RefreshCw, X } from "lucide-react";
import { PoweredByAirweave } from "./PoweredByAirweave";
import type { SessionError, SessionErrorCode } from "../lib/types";

interface ErrorScreenProps {
  error: SessionError;
  onRetry?: () => void;
  onClose?: () => void;
}

const errorMessages: Record<
  SessionErrorCode,
  { title: string; description: string }
> = {
  invalid_token: {
    title: "Invalid Session",
    description: "The session token is invalid. Please try again.",
  },
  expired_token: {
    title: "Session Expired",
    description: "Your session has expired. Please refresh and try again.",
  },
  network_error: {
    title: "Connection Error",
    description:
      "Unable to connect to the server. Please check your connection.",
  },
  session_mismatch: {
    title: "Session Mismatch",
    description: "The session ID does not match. Please try again.",
  },
};

export function ErrorScreen({ error, onRetry, onClose }: ErrorScreenProps) {
  const errorInfo = errorMessages[error.code] || {
    title: "Error",
    description: error.message,
  };

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-6 pb-12 text-center relative"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
      <div className="flex items-center justify-center mx-auto mb-4">
        <AlertCircle
          className="w-12 h-12"
          strokeWidth={1}
          style={{ color: "var(--connect-error)" }}
        />
      </div>
      <h1
        className="font-medium text-lg mb-2"
        style={{ color: "var(--connect-text)" }}
      >
        {errorInfo.title}
      </h1>
      <p className="mb-6" style={{ color: "var(--connect-text-muted)" }}>
        {errorInfo.description}
      </p>
      <div className="flex gap-3 justify-center">
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-4 py-1.5 font-medium rounded-md text-sm transition-colors flex items-center gap-2"
            style={{
              backgroundColor: "var(--connect-primary)",
              color: "white",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.backgroundColor =
                "var(--connect-primary-hover)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.backgroundColor = "var(--connect-primary)")
            }
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        )}
        {onClose && (
          <button
            onClick={onClose}
            className="px-4 py-1.5 font-medium rounded-md text-sm transition-colors flex items-center gap-2"
            style={{
              backgroundColor: "var(--connect-secondary)",
              color: "var(--connect-text)",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.backgroundColor =
                "var(--connect-secondary-hover)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.backgroundColor =
                "var(--connect-secondary)")
            }
          >
            <X className="w-4 h-4" />
            Close
          </button>
        )}
      </div>
      <PoweredByAirweave />
    </div>
  );
}
