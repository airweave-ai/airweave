import { useCallback, useEffect, useRef, useState } from "react";
import { useParentMessaging } from "../hooks/useParentMessaging";
import { apiClient, ApiError } from "../lib/api";
import { ThemeProvider, useTheme } from "../lib/theme";
import type {
  ConnectSessionContext,
  ConnectTheme,
  NavigateView,
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
  // Read initial theme from URL parameter for immediate loading state styling
  const initialTheme = (() => {
    if (typeof window === "undefined") return undefined;
    const params = new URLSearchParams(window.location.search);
    const themeParam = params.get("theme");
    if (themeParam === "light" || themeParam === "dark" || themeParam === "system") {
      return { mode: themeParam } as ConnectTheme;
    }
    return undefined;
  })();

  return (
    <ThemeProvider initialTheme={initialTheme}>
      <SessionContent />
    </ThemeProvider>
  );
}

function SessionContent() {
  const [status, setStatus] = useState<SessionStatus>({ status: "idle" });
  const [session, setSession] = useState<ConnectSessionContext | null>(null);
  const [navigateView, setNavigateView] = useState<NavigateView | null>(null);
  const { setTheme } = useTheme();
  const hasInitialized = useRef(false);
  const validateSessionRef = useRef<
    ((token: string, isRetry?: boolean) => Promise<boolean>) | undefined
  >(undefined);

  // Handle theme changes from parent (both initial and dynamic updates)
  const handleThemeChange = useCallback(
    (theme: ConnectTheme) => {
      setTheme(theme);
    },
    [setTheme],
  );

  // Handle navigation from parent
  const handleNavigate = useCallback((view: NavigateView) => {
    setNavigateView(view);
  }, []);

  const {
    isConnected,
    requestToken,
    notifyStatusChange,
    notifyConnectionCreated,
    requestClose,
  } = useParentMessaging({
    onThemeChange: handleThemeChange,
    onNavigate: handleNavigate,
  });

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
            return validateSessionRef.current!(response.token, true);
          }
        }

        setStatus({ status: "error", error });
        return false;
      }
    },
    [requestToken, handleThemeChange],
  );

  // Keep ref up to date for recursive calls
  useEffect(() => {
    validateSessionRef.current = validateSession;
  });

  // Request token from parent when connected (only once)
  useEffect(() => {
    if (!isConnected || hasInitialized.current) return;
    hasInitialized.current = true;

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
    return <LoadingScreen />;
  }

  if (status.status === "validating") {
    return <LoadingScreen />;
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
    return (
      <SuccessScreen
        session={session}
        initialView={navigateView}
        onViewChange={setNavigateView}
        onConnectionCreated={notifyConnectionCreated}
      />
    );
  }

  return <LoadingScreen />;
}
