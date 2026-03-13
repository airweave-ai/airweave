import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "./api";
import { isPopupOpen, listenForOAuthComplete, openOAuthPopup } from "./oauth";
import type {
  OAuthCallbackResult,
  OAuthFlowStatus,
  SourceConnectionCreateRequest,
} from "./types";

interface UseOAuthFlowOptions {
  shortName: string;
  sourceName: string;
  collectionId: string;
  configValues: Record<string, unknown>;
  byocValues?: { client_id: string; client_secret: string };
  requiresByoc: boolean;
  syncImmediately?: boolean;
  onSuccess: (connectionId: string) => void;
  onCancel?: () => void;
}

interface UseOAuthFlowResult {
  status: OAuthFlowStatus;
  error: string | null;
  blockedAuthUrl: string | null;
  initiateOAuth: () => Promise<void>;
  retryPopup: () => void;
  handleManualLinkClick: () => void;
}

export function useOAuthFlow({
  shortName,
  sourceName,
  collectionId,
  configValues,
  byocValues,
  requiresByoc,
  syncImmediately = true,
  onSuccess,
  onCancel,
}: UseOAuthFlowOptions): UseOAuthFlowResult {
  const [status, setStatus] = useState<OAuthFlowStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [blockedAuthUrl, setBlockedAuthUrl] = useState<string | null>(null);
  const popupRef = useRef<Window | null>(null);
  // Ref to synchronously track OAuth completion, preventing race condition
  // where interval could override successful result before React re-renders
  const oauthCompletedRef = useRef(false);
  // Track the connection ID created in this OAuth flow for cleanup on cancel
  const createdConnectionIdRef = useRef<string | null>(null);

  const handleOAuthResult = useCallback(
    (result: OAuthCallbackResult) => {
      // Mark OAuth as completed synchronously to prevent race condition with interval
      oauthCompletedRef.current = true;

      if (popupRef.current && !popupRef.current.closed) {
        popupRef.current.close();
      }
      popupRef.current = null;

      if (result.status === "success" && result.source_connection_id) {
        // Clear the ref since OAuth succeeded - don't delete the connection
        createdConnectionIdRef.current = null;
        setStatus("idle");
        onSuccess(result.source_connection_id);
      } else {
        setStatus("error");
        setError(
          result.error_message ??
            "OAuth authentication failed. Please try again.",
        );
      }
    },
    [onSuccess],
  );

  useEffect(() => {
    if (status !== "waiting" && status !== "popup_blocked") return;

    const cleanup = listenForOAuthComplete(handleOAuthResult);

    let pollInterval: ReturnType<typeof setInterval> | undefined;
    if (status === "waiting") {
      pollInterval = setInterval(() => {
        // Check oauthCompletedRef to avoid race condition where OAuth completed
        // but React hasn't re-rendered yet (stale status in closure)
        if (!isPopupOpen(popupRef.current) && !oauthCompletedRef.current) {
          // User closed popup without completing OAuth
          createdConnectionIdRef.current = null;
          popupRef.current = null;
          setStatus("idle");
          onCancel?.();
        }
      }, 500);
    }

    return () => {
      cleanup();
      if (pollInterval) clearInterval(pollInterval);
      // Close popup if still open when component unmounts or status changes
      if (popupRef.current && !popupRef.current.closed) {
        popupRef.current.close();
        popupRef.current = null;
      }
    };
  }, [status, handleOAuthResult, onCancel]);

  const initiateOAuth = useCallback(async () => {
    setStatus("creating");
    setError(null);
    oauthCompletedRef.current = false;

    try {
      const currentOrigin = window.location.origin;
      const redirectUri = `${currentOrigin}/oauth-callback`;

      const payload: SourceConnectionCreateRequest = {
        short_name: shortName,
        name: sourceName,
        readable_collection_id: collectionId,
        redirect_url: redirectUri, // Where to redirect after OAuth completes
        sync_immediately: syncImmediately,
        authentication: {
          redirect_uri: redirectUri,
          ...(requiresByoc &&
            byocValues && {
              client_id: byocValues.client_id.trim(),
              client_secret: byocValues.client_secret.trim(),
            }),
        },
      };

      if (Object.keys(configValues).length > 0) {
        payload.config = configValues;
      }

      const response = await apiClient.createSourceConnection(payload);
      // Track the created connection for cleanup if user cancels
      createdConnectionIdRef.current = response.id;

      if (response.auth?.auth_url) {
        setStatus("waiting");
        const popup = openOAuthPopup({ url: response.auth.auth_url });

        if (!popup) {
          setStatus("popup_blocked");
          setBlockedAuthUrl(response.auth.auth_url);
          return;
        }

        popupRef.current = popup;
      } else {
        setStatus("error");
        setError("Failed to get authorization URL. Please try again.");
      }
    } catch (err) {
      setStatus("error");
      setError(
        err instanceof Error ? err.message : "Failed to initiate OAuth flow",
      );
    }
  }, [
    shortName,
    sourceName,
    collectionId,
    configValues,
    byocValues,
    requiresByoc,
    syncImmediately,
  ]);

  const retryPopup = useCallback(() => {
    if (!blockedAuthUrl) return;

    const popup = openOAuthPopup({ url: blockedAuthUrl });
    if (popup) {
      popupRef.current = popup;
      setStatus("waiting");
      setBlockedAuthUrl(null);
    }
  }, [blockedAuthUrl]);

  const handleManualLinkClick = useCallback(() => {
    setStatus("waiting");
  }, []);

  return {
    status,
    error,
    blockedAuthUrl,
    initiateOAuth,
    retryPopup,
    handleManualLinkClick,
  };
}
