/**
 * Validates that a URL path is a safe same-origin redirect target.
 *
 * Rejects absolute URLs, protocol-relative URLs ("//evil.com"),
 * and anything that would navigate away from the current origin.
 */
export function isSafeRedirectPath(path: string): boolean {
  if (!path.startsWith("/") || path.startsWith("//")) {
    return false;
  }
  try {
    const url = new URL(path, window.location.origin);
    return url.origin === window.location.origin;
  } catch {
    return false;
  }
}

/**
 * Returns the given path if it is a safe same-origin redirect,
 * otherwise returns the provided fallback.
 */
export function safeRedirectPath(path: string, fallback: string): string {
  return isSafeRedirectPath(path) ? path : fallback;
}
