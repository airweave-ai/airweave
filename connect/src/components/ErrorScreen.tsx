import { AlertCircle, RefreshCw, X } from "lucide-react";
import { useTheme } from "../lib/theme";
import type { ConnectLabels, SessionError, SessionErrorCode } from "../lib/types";
import { Button } from "./Button";
import { PageLayout } from "./PageLayout";

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
    <PageLayout title={errorInfo.title} centerContent>
      <div className="flex items-center justify-center mx-auto mb-4">
        <AlertCircle
          className="w-12 h-12"
          strokeWidth={1}
          style={{ color: "var(--connect-error)" }}
        />
      </div>
      <p className="mb-6" style={{ color: "var(--connect-text-muted)" }}>
        {errorInfo.description}
      </p>
      <div className="flex gap-3 justify-center">
        {onRetry && (
          <Button onClick={onRetry}>
            <RefreshCw className="w-4 h-4" />
            {labels.buttonRetry}
          </Button>
        )}
        {onClose && (
          <Button onClick={onClose} variant="secondary">
            <X className="w-4 h-4" />
            {labels.buttonClose}
          </Button>
        )}
      </div>
    </PageLayout>
  );
}
