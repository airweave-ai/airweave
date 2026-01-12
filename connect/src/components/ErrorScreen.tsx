import { AlertCircle, RefreshCw, X } from "lucide-react";
import { useTheme } from "../lib/theme";
import type { ConnectLabels, SessionError, SessionErrorCode } from "../lib/types";
import { PoweredByAirweave } from "./PoweredByAirweave";

interface ErrorScreenProps {
  error: SessionError;
  onRetry?: () => void;
  onClose?: () => void;
}

function getErrorInfo(
  errorCode: SessionErrorCode,
  labels: Required<ConnectLabels>,
  fallbackMessage: string,
): { title: string; description: string } {
  switch (errorCode) {
    case "invalid_token":
      return {
        title: labels.errorInvalidTokenTitle,
        description: labels.errorInvalidTokenDescription,
      };
    case "expired_token":
      return {
        title: labels.errorExpiredTokenTitle,
        description: labels.errorExpiredTokenDescription,
      };
    case "network_error":
      return {
        title: labels.errorNetworkTitle,
        description: labels.errorNetworkDescription,
      };
    case "session_mismatch":
      return {
        title: labels.errorSessionMismatchTitle,
        description: labels.errorSessionMismatchDescription,
      };
    default:
      return {
        title: labels.errorDefaultTitle,
        description: fallbackMessage,
      };
  }
}

export function ErrorScreen({ error, onRetry, onClose }: ErrorScreenProps) {
  const { labels } = useTheme();
  const errorInfo = getErrorInfo(error.code, labels, error.message);

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
            {labels.buttonRetry}
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
            {labels.buttonClose}
          </button>
        )}
      </div>
      <PoweredByAirweave />
    </div>
  );
}
