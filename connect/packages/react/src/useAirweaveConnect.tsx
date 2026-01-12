import type {
  ChildToParentMessage,
  ConnectTheme,
  ParentToChildMessage,
  SessionError,
  SessionStatus,
} from "airweave-connect/lib/types";
import { useCallback, useEffect, useRef, useState } from "react";
import { createRoot, Root } from "react-dom/client";
import { ConnectModal } from "./ConnectModal";
import { DEFAULT_CONNECT_URL } from "./constants";

export interface UseAirweaveConnectOptions {
  /** Async function to get a session token from your backend */
  getSessionToken: () => Promise<string>;
  /** Theme configuration for the Connect UI */
  theme?: ConnectTheme;
  /** URL of the hosted Connect iframe (defaults to Airweave hosted) */
  connectUrl?: string;
  /** Called when a connection is successfully created */
  onSuccess?: (connectionId: string) => void;
  /** Called when an error occurs */
  onError?: (error: SessionError) => void;
  /** Called when the modal is closed */
  onClose?: (reason: "success" | "cancel" | "error") => void;
  /** Called when a new connection is created */
  onConnectionCreated?: (connectionId: string) => void;
  /** Called when the session status changes */
  onStatusChange?: (status: SessionStatus) => void;
}

export interface UseAirweaveConnectReturn {
  /** Open the Connect modal */
  open: () => void;
  /** Close the Connect modal */
  close: () => void;
  /** Whether the modal is currently open */
  isOpen: boolean;
  /** Whether a token is being fetched */
  isLoading: boolean;
  /** Current error, if any */
  error: SessionError | null;
  /** Current session status from the iframe */
  status: SessionStatus | null;
}

const CONTAINER_ID = "airweave-connect-root";

export function useAirweaveConnect(
  options: UseAirweaveConnectOptions,
): UseAirweaveConnectReturn {
  const {
    getSessionToken,
    theme,
    connectUrl = DEFAULT_CONNECT_URL,
    onSuccess,
    onError,
    onClose,
    onConnectionCreated,
    onStatusChange,
  } = options;

  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<SessionError | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);

  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const sessionTokenRef = useRef<string | null>(null);
  const rootRef = useRef<Root | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Derive expected origin from connectUrl for secure postMessage
  const expectedOrigin = (() => {
    try {
      const url = new URL(connectUrl);
      return url.origin;
    } catch {
      // Fallback for invalid URLs - will cause postMessage to fail safely
      return connectUrl;
    }
  })();

  // Store callbacks in refs to avoid re-creating message handler
  const callbacksRef = useRef({
    onSuccess,
    onError,
    onClose,
    onConnectionCreated,
    onStatusChange,
  });
  callbacksRef.current = {
    onSuccess,
    onError,
    onClose,
    onConnectionCreated,
    onStatusChange,
  };

  // Store theme in ref to use in message handler
  const themeRef = useRef(theme);
  themeRef.current = theme;

  // Send message to iframe with restricted origin
  const sendToIframe = useCallback(
    (message: ParentToChildMessage) => {
      iframeRef.current?.contentWindow?.postMessage(message, expectedOrigin);
    },
    [expectedOrigin],
  );

  const handleClose = useCallback(
    (reason: "success" | "cancel" | "error" = "cancel") => {
      setIsOpen(false);
      sessionTokenRef.current = null;
      callbacksRef.current.onClose?.(reason);
    },
    [],
  );

  // Handle messages from iframe
  useEffect(() => {
    if (!isOpen) return;

    const handleMessage = (event: MessageEvent) => {
      // Validate origin to prevent spoofed messages from malicious sites
      if (event.origin !== expectedOrigin) {
        return;
      }

      const data = event.data as ChildToParentMessage;
      if (!data || typeof data !== "object" || !("type" in data)) {
        return;
      }

      switch (data.type) {
        case "CONNECT_READY":
          // Iframe is ready
          break;

        case "REQUEST_TOKEN":
          if (sessionTokenRef.current) {
            sendToIframe({
              type: "TOKEN_RESPONSE",
              requestId: data.requestId,
              token: sessionTokenRef.current,
              theme: themeRef.current,
            });
          } else {
            sendToIframe({
              type: "TOKEN_ERROR",
              requestId: data.requestId,
              error: "No session token available",
            });
          }
          break;

        case "STATUS_CHANGE":
          setStatus(data.status);
          callbacksRef.current.onStatusChange?.(data.status);

          if (data.status.status === "error") {
            setError(data.status.error);
            callbacksRef.current.onError?.(data.status.error);
          }
          break;

        case "CONNECTION_CREATED":
          callbacksRef.current.onConnectionCreated?.(data.connectionId);
          callbacksRef.current.onSuccess?.(data.connectionId);
          break;

        case "CLOSE":
          handleClose(data.reason);
          break;
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [isOpen, handleClose, sendToIframe, expectedOrigin]);

  // Build the iframe URL with theme query parameter
  const iframeUrl = (() => {
    const url = new URL(connectUrl);
    if (theme?.mode) {
      url.searchParams.set("theme", theme.mode);
    }
    return url.toString();
  })();

  // Manage modal rendering via createRoot
  useEffect(() => {
    if (isOpen) {
      // Create container if it doesn't exist
      if (!containerRef.current) {
        containerRef.current = document.createElement("div");
        containerRef.current.id = CONTAINER_ID;
        document.body.appendChild(containerRef.current);
      }

      // Create root if it doesn't exist
      if (!rootRef.current) {
        rootRef.current = createRoot(containerRef.current);
      }

      // Render modal
      rootRef.current.render(
        <ConnectModal
          connectUrl={iframeUrl}
          onClose={() => handleClose("cancel")}
          onIframeRef={(iframe) => {
            iframeRef.current = iframe;
          }}
        />,
      );
    } else {
      // Unmount modal
      if (rootRef.current) {
        rootRef.current.render(<></>);
      }
    }
  }, [isOpen, iframeUrl, handleClose]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (rootRef.current) {
        rootRef.current.unmount();
        rootRef.current = null;
      }
      if (containerRef.current && containerRef.current.parentNode) {
        containerRef.current.parentNode.removeChild(containerRef.current);
        containerRef.current = null;
      }
    };
  }, []);

  const open = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const token = await getSessionToken();
      sessionTokenRef.current = token;
      setIsOpen(true);
    } catch (err) {
      const sessionError: SessionError = {
        code: "network_error",
        message:
          err instanceof Error ? err.message : "Failed to get session token",
      };
      setError(sessionError);
      callbacksRef.current.onError?.(sessionError);
    } finally {
      setIsLoading(false);
    }
  }, [getSessionToken]);

  const close = useCallback(() => {
    handleClose("cancel");
  }, [handleClose]);

  return {
    open,
    close,
    isOpen,
    isLoading,
    error,
    status,
  };
}
