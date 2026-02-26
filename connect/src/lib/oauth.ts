import type { OAuthCallbackResult } from "./types";

export interface OAuthPopupOptions {
  url: string;
  width?: number;
  height?: number;
}

/**
 * Opens a centered popup window for OAuth authorization.
 * Returns null if popup was blocked.
 */
export function openOAuthPopup(options: OAuthPopupOptions): Window | null {
  const { url, width = 600, height = 700 } = options;

  // Calculate center position
  const left = window.screenX + (window.outerWidth - width) / 2;
  const top = window.screenY + (window.outerHeight - height) / 2;

  return window.open(
    url,
    "oauth-popup",
    `width=${width},height=${height},left=${left},top=${top},scrollbars=yes,resizable=yes`
  );
}

/**
 * Listens for OAuth completion message from popup window.
 * Returns a cleanup function to remove the listener.
 *
 * @param callback - Function to call with OAuth result
 * @param expectedOrigin - Optional origin to validate against (defaults to current origin for same-origin popups)
 */
export function listenForOAuthComplete(
  callback: (result: OAuthCallbackResult) => void,
  expectedOrigin?: string
): () => void {
  // Default to current origin since OAuth popup is same-origin
  const validOrigin = expectedOrigin ?? window.location.origin;

  const handler = (event: MessageEvent) => {
    // Validate origin to prevent spoofed OAuth messages from other windows
    if (event.origin !== validOrigin) {
      return;
    }

    // Only handle OAUTH_COMPLETE messages
    if (event.data?.type === "OAUTH_COMPLETE") {
      const result: OAuthCallbackResult = {
        status: event.data.status,
        source_connection_id: event.data.source_connection_id,
        error_type: event.data.error_type,
        error_message: event.data.error_message,
      };
      callback(result);
    }
  };

  window.addEventListener("message", handler);
  return () => window.removeEventListener("message", handler);
}

/**
 * Checks if a popup window is still open.
 */
export function isPopupOpen(popup: Window | null): boolean {
  return popup !== null && !popup.closed;
}
