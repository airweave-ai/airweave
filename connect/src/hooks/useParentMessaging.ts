import { useCallback, useRef, useState, useEffect } from "react";
import type {
  ChildToParentMessage,
  ConnectTheme,
  NavigateView,
  ParentToChildMessage,
  SessionStatus,
} from "../lib/types";

interface TokenResponse {
  token: string;
  theme?: ConnectTheme;
}

interface UseParentMessagingOptions {
  onThemeChange?: (theme: ConnectTheme) => void;
  onNavigate?: (view: NavigateView) => void;
}

interface UseParentMessagingReturn {
  isConnected: boolean;
  requestToken: () => Promise<TokenResponse | null>;
  notifyStatusChange: (status: SessionStatus) => void;
  notifyConnectionCreated: (connectionId: string) => void;
  requestClose: (reason: "success" | "cancel" | "error") => void;
}

interface PendingRequest {
  resolve: (value: TokenResponse | null) => void;
  reject: (error: Error) => void;
}

// Check if running in iframe (runs once at module load for SSR safety)
function isInIframe(): boolean {
  if (typeof window === "undefined") return false;
  return window.parent !== window;
}

export function useParentMessaging(
  options?: UseParentMessagingOptions,
): UseParentMessagingReturn {
  // Initialize to true if we're in an iframe, since connection is instant
  const [isConnected, setIsConnected] = useState(() => isInIframe());
  const pendingRequests = useRef<Map<string, PendingRequest>>(new Map());
  const hasInitialized = useRef(false);
  const onThemeChangeRef = useRef(options?.onThemeChange);
  const onNavigateRef = useRef(options?.onNavigate);

  // Store the validated parent origin for secure postMessage communication
  const parentOriginRef = useRef<string | null>(null);

  // Keep the callback refs up to date
  useEffect(() => {
    onThemeChangeRef.current = options?.onThemeChange;
    onNavigateRef.current = options?.onNavigate;
  });

  // Helper to send messages to parent with validated origin
  const sendToParent = useCallback((message: ChildToParentMessage) => {
    if (typeof window !== "undefined" && window.parent !== window) {
      // Use validated parent origin, fall back to "*" only for initial CONNECT_READY
      const targetOrigin = parentOriginRef.current || "*";
      window.parent.postMessage(message, targetOrigin);
    }
  }, []);

  useEffect(() => {
    // Only run in browser
    if (typeof window === "undefined") return;

    // Check if we're in an iframe
    if (window.parent === window) {
      console.warn("Not running in an iframe, parent messaging skipped");
      return;
    }

    const handleMessage = (event: MessageEvent<ParentToChildMessage>) => {
      const { data } = event;

      if (!data || typeof data !== "object" || !("type" in data)) {
        return;
      }

      // Capture parent origin from the first TOKEN_RESPONSE message
      // This establishes the trusted origin for all future communication
      if (
        (data.type === "TOKEN_RESPONSE" || data.type === "TOKEN_ERROR") &&
        !parentOriginRef.current
      ) {
        parentOriginRef.current = event.origin;
      }

      // Validate origin for all messages once we have a trusted origin
      // This prevents other windows from spoofing messages
      if (parentOriginRef.current && event.origin !== parentOriginRef.current) {
        return;
      }

      switch (data.type) {
        case "TOKEN_RESPONSE": {
          const pending = pendingRequests.current.get(data.requestId);
          if (pending) {
            pending.resolve({ token: data.token, theme: data.theme });
            pendingRequests.current.delete(data.requestId);
          }
          break;
        }
        case "TOKEN_ERROR": {
          const pending = pendingRequests.current.get(data.requestId);
          if (pending) {
            pending.resolve(null);
            pendingRequests.current.delete(data.requestId);
          }
          break;
        }
        case "SET_THEME": {
          if (onThemeChangeRef.current) {
            onThemeChangeRef.current(data.theme);
          }
          break;
        }
        case "NAVIGATE": {
          if (onNavigateRef.current) {
            onNavigateRef.current(data.view);
          }
          break;
        }
      }
    };

    window.addEventListener("message", handleMessage);

    // Signal ready to parent (only once)
    if (!hasInitialized.current) {
      hasInitialized.current = true;
      sendToParent({ type: "CONNECT_READY" });
    }

    return () => {
      window.removeEventListener("message", handleMessage);
      setIsConnected(false);
    };
  }, [sendToParent]);

  const requestToken = useCallback(async (): Promise<TokenResponse | null> => {
    if (typeof window === "undefined" || window.parent === window) {
      return null;
    }

    const requestId = crypto.randomUUID();

    return new Promise<TokenResponse | null>((resolve, reject) => {
      pendingRequests.current.set(requestId, { resolve, reject });

      sendToParent({ type: "REQUEST_TOKEN", requestId });

      // Timeout after 10 seconds
      setTimeout(() => {
        if (pendingRequests.current.has(requestId)) {
          pendingRequests.current.delete(requestId);
          resolve(null);
        }
      }, 10000);
    });
  }, [sendToParent]);

  const notifyStatusChange = useCallback(
    (status: SessionStatus) => {
      sendToParent({ type: "STATUS_CHANGE", status });
    },
    [sendToParent],
  );

  const notifyConnectionCreated = useCallback(
    (connectionId: string) => {
      sendToParent({ type: "CONNECTION_CREATED", connectionId });
    },
    [sendToParent],
  );

  const requestClose = useCallback(
    (reason: "success" | "cancel" | "error") => {
      sendToParent({ type: "CLOSE", reason });
    },
    [sendToParent],
  );

  return {
    isConnected,
    requestToken,
    notifyStatusChange,
    notifyConnectionCreated,
    requestClose,
  };
}
