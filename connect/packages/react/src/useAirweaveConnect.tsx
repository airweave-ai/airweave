import type {
  ChildToParentMessage,
  ConnectTheme,
  NavigateView,
  ParentToChildMessage,
  SessionError,
  SessionStatus,
} from "airweave-connect/lib/types";
import { useCallback, useEffect, useRef, useState } from "react";
import { createRoot, Root } from "react-dom/client";
import { ConnectModal } from "./ConnectModal";
import { DEFAULT_CONNECT_URL } from "./constants";
import { buildIframeUrl, getExpectedOrigin } from "./iframeUrl";
import type {
  UseAirweaveConnectOptions,
  UseAirweaveConnectReturn,
} from "./useAirweaveConnect.types";

// Re-export types for consumers
export type { ModalStyle, UseAirweaveConnectOptions, UseAirweaveConnectReturn } from "./useAirweaveConnect.types";

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
    initialView,
    modalStyle,
    showCloseButton = false,
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
  const expectedOrigin = getExpectedOrigin(connectUrl);

  // Store callbacks and getSessionToken in refs to avoid re-creating message handler
  const getSessionTokenRef = useRef(getSessionToken);
  getSessionTokenRef.current = getSessionToken;

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

  // Store initialView in ref to use on CONNECT_READY
  const initialViewRef = useRef(initialView);
  initialViewRef.current = initialView;

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
          // Iframe is ready - navigate to initial view if specified
          if (initialViewRef.current) {
            sendToIframe({ type: "NAVIGATE", view: initialViewRef.current });
          }
          break;

        case "REQUEST_TOKEN": {
          // Re-fetch token from the customer's backend to handle expiry/refresh
          const requestId = data.requestId;
          getSessionTokenRef
            .current()
            .then((token) => {
              sessionTokenRef.current = token;
              sendToIframe({
                type: "TOKEN_RESPONSE",
                requestId,
                token,
                theme: themeRef.current,
              });
            })
            .catch(() => {
              sendToIframe({
                type: "TOKEN_ERROR",
                requestId,
                error: "Failed to refresh session token",
              });
            });
          break;
        }

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
  const iframeUrl = buildIframeUrl(connectUrl, theme);

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
          modalStyle={modalStyle}
          showCloseButton={showCloseButton}
        />,
      );
    } else {
      // Unmount modal
      if (rootRef.current) {
        rootRef.current.render(<></>);
      }
    }
  }, [isOpen, iframeUrl, handleClose, modalStyle, showCloseButton]);

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

  const setTheme = useCallback(
    (newTheme: ConnectTheme) => {
      themeRef.current = newTheme;
      sendToIframe({ type: "SET_THEME", theme: newTheme });
    },
    [sendToIframe],
  );

  const navigate = useCallback(
    (view: NavigateView) => {
      sendToIframe({ type: "NAVIGATE", view });
    },
    [sendToIframe],
  );

  return {
    open,
    close,
    setTheme,
    navigate,
    isOpen,
    isLoading,
    error,
    status,
  };
}
