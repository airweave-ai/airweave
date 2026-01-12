import { AlertCircle, RefreshCw, X } from "lucide-react";
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
      className="min-h-screen flex flex-col items-center justify-center p-6 text-center"
      style={{ backgroundColor: 'var(--connect-bg)' }}
    >
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6"
        style={{ backgroundColor: 'color-mix(in srgb, var(--connect-error) 20%, transparent)' }}
      >
        <AlertCircle className="w-8 h-8" style={{ color: 'var(--connect-error)' }} />
      </div>
      <h1 className="text-2xl font-bold mb-2" style={{ color: 'var(--connect-text)' }}>
        {errorInfo.title}
      </h1>
      <p className="mb-6" style={{ color: 'var(--connect-text-muted)' }}>
        {errorInfo.description}
      </p>
      <div className="flex gap-3 justify-center">
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-6 py-2 font-semibold rounded-lg transition-colors flex items-center gap-2"
            style={{
              backgroundColor: 'var(--connect-primary)',
              color: 'white',
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--connect-primary-hover)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--connect-primary)'}
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
        )}
        {onClose && (
          <button
            onClick={onClose}
            className="px-6 py-2 font-semibold rounded-lg transition-colors flex items-center gap-2"
            style={{
              backgroundColor: 'var(--connect-secondary)',
              color: 'var(--connect-text)',
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--connect-secondary-hover)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--connect-secondary)'}
          >
            <X className="w-4 h-4" />
            Close
          </button>
        )}
      </div>
    </div>
  );
}
