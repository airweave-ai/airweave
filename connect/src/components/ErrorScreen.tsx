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
    <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-6 text-center">
      <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
        <AlertCircle className="w-8 h-8 text-red-400" />
      </div>
      <h1 className="text-2xl font-bold text-white mb-2">{errorInfo.title}</h1>
      <p className="text-gray-400 mb-6">{errorInfo.description}</p>
      <div className="flex gap-3 justify-center">
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-6 py-2 bg-cyan-500 hover:bg-cyan-600 text-white font-semibold rounded-lg transition-colors flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
        )}
        {onClose && (
          <button
            onClick={onClose}
            className="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white font-semibold rounded-lg transition-colors flex items-center gap-2"
          >
            <X className="w-4 h-4" />
            Close
          </button>
        )}
      </div>
    </div>
  );
}
