import { useCallback, useEffect, useState } from "react";
import { useParentMessaging } from "../hooks/useParentMessaging";
import { apiClient, ApiError } from "../lib/api";
import { ThemeProvider, useTheme } from "../lib/theme";
import type {
  ConnectSessionContext,
  ConnectTheme,
  SessionError,
  SessionStatus,
} from "../lib/types";
import { ErrorScreen } from "./ErrorScreen";
import { LoadingScreen } from "./LoadingScreen";
import { SuccessScreen } from "./SuccessScreen";

function extractSessionIdFromToken(token: string): string | null {
  // The token is HMAC-signed state that contains session_id
  // Format: base64(json_payload).signature
  try {
    const [payload] = token.split(".");
    const decoded = JSON.parse(atob(payload));
    return decoded.sid || null;
  } catch {
    return null;
  }
}

export function SessionProvider() {
  const [theme, setTheme] = useState<ConnectTheme | undefined>(undefined);

  return (
    <ThemeProvider initialTheme={theme}>
      <SessionContent onThemeReceived={setTheme} />
    </ThemeProvider>
  );
}

interface SessionContentProps {
  onThemeReceived: (theme: ConnectTheme) => void;
}

function SessionContent({ onThemeReceived }: SessionContentProps) {
  const [status, setStatus] = useState<SessionStatus>({ status: "idle" });
  const [session, setSession] = useState<ConnectSessionContext | null>(null);
  const { setTheme } = useTheme();

  // Handle theme changes from parent (both initial and dynamic updates)
  const handleThemeChange = useCallback(
    (theme: ConnectTheme) => {
      setTheme(theme);
      onThemeReceived(theme);
    },
    [setTheme, onThemeReceived],
  );

  const { isConnected, requestToken, notifyStatusChange, requestClose } =
    useParentMessaging({ onThemeChange: handleThemeChange });

  // Update parent when status changes
  useEffect(() => {
    notifyStatusChange(status);
  }, [status, notifyStatusChange]);

  const validateSession = useCallback(
    async (token: string, isRetry = false): Promise<boolean> => {
      setStatus({ status: "validating" });

      // Set token for API client
      apiClient.setToken(token);

      // Extract session ID from token
      const sessionId = extractSessionIdFromToken(token);
      if (!sessionId) {
        const error: SessionError = {
          code: "invalid_token",
          message: "Could not extract session ID from token",
        };
        setStatus({ status: "error", error });
        return false;
      }

      try {
        const sessionContext = await apiClient.validateSession(sessionId);
        setSession(sessionContext);
        setStatus({ status: "valid", session: sessionContext });
        return true;
      } catch (err) {
        let error: SessionError;
        let shouldRetry = false;

        if (err instanceof ApiError) {
          if (err.status === 401) {
            // Check if it's an expiration error
            const isExpired = err.message.toLowerCase().includes("expired");
            error = {
              code: isExpired ? "expired_token" : "invalid_token",
              message: err.message,
            };
            // Auto-retry on expired/invalid token (but only once)
            shouldRetry = !isRetry;
          } else if (err.status === 403) {
            error = { code: "session_mismatch", message: err.message };
          } else {
            error = { code: "network_error", message: err.message };
          }
        } else {
          error = { code: "network_error", message: "Unknown error occurred" };
        }

        // If we should retry, request a new token from parent
        if (shouldRetry) {
          setStatus({ status: "waiting_for_token" });
          const response = await requestToken();
          if (response) {
            if (response.theme) {
              handleThemeChange(response.theme);
            }
            return validateSession(response.token, true);
          }
        }

        setStatus({ status: "error", error });
        return false;
      }
    },
    [requestToken, handleThemeChange],
  );

  // Request token from parent when connected
  useEffect(() => {
    if (!isConnected) return;

    const init = async () => {
      setStatus({ status: "waiting_for_token" });

      const response = await requestToken();
      if (response) {
        // Apply theme if provided
        if (response.theme) {
          handleThemeChange(response.theme);
        }
        await validateSession(response.token);
      } else {
        setStatus({
          status: "error",
          error: {
            code: "invalid_token",
            message: "No session token provided by parent",
          },
        });
      }
    };

    init();
  }, [isConnected, requestToken, validateSession, handleThemeChange]);

  const handleRetry = useCallback(async () => {
    setStatus({ status: "waiting_for_token" });
    const response = await requestToken();
    if (response) {
      if (response.theme) {
        handleThemeChange(response.theme);
      }
      await validateSession(response.token);
    }
  }, [requestToken, validateSession, handleThemeChange]);

  const handleClose = useCallback(() => {
    requestClose("cancel");
  }, [requestClose]);

  // Render based on status
  if (status.status === "idle" || status.status === "waiting_for_token") {
    return <LoadingScreen message="Connecting..." />;
  }

  if (status.status === "validating") {
    return <LoadingScreen message="Validating session..." />;
  }

  if (status.status === "error") {
    return (
      <ErrorScreen
        error={status.error}
        onRetry={handleRetry}
        onClose={handleClose}
      />
    );
  }

  if (status.status === "valid" && session) {
    // For now, show success screen. Later this will render children (integration list)
    return <SuccessScreen session={session} />;
  }

  return <LoadingScreen />;
}
