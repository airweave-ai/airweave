import type { ConnectTheme } from "airweave-connect/lib/types";

/**
 * Builds the iframe URL with theme query parameter.
 */
export function buildIframeUrl(connectUrl: string, theme?: ConnectTheme): string {
  const url = new URL(connectUrl);
  if (theme?.mode) {
    url.searchParams.set("theme", theme.mode);
  }
  return url.toString();
}

/**
 * Derives the expected origin from a connect URL for secure postMessage validation.
 */
export function getExpectedOrigin(connectUrl: string): string {
  try {
    const url = new URL(connectUrl);
    return url.origin;
  } catch {
    // Fallback for invalid URLs - will cause postMessage to fail safely
    return connectUrl;
  }
}
