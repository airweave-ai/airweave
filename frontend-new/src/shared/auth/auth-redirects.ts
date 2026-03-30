export function getAuthCallbackRedirectTarget({
  callbackPath,
  searchParams,
}: {
  callbackPath: string;
  searchParams: Record<string, string | undefined>;
}) {
  const callbackUrl = new URL(callbackPath, window.location.origin);

  for (const [key, value] of Object.entries(searchParams)) {
    if (!value) {
      continue;
    }

    callbackUrl.searchParams.set(key, value);
  }

  return `${callbackUrl.pathname}${callbackUrl.search}${callbackUrl.hash}`;
}

export function getSafeRedirectTarget({
  fallbackTarget,
  redirectTarget,
}: {
  fallbackTarget: string;
  redirectTarget?: string;
}) {
  if (!redirectTarget) {
    return fallbackTarget;
  }

  if (redirectTarget.startsWith('/') && !redirectTarget.startsWith('//')) {
    return redirectTarget;
  }

  try {
    const targetUrl = new URL(redirectTarget, window.location.origin);

    if (targetUrl.origin !== window.location.origin) {
      return fallbackTarget;
    }

    return `${targetUrl.pathname}${targetUrl.search}${targetUrl.hash}`;
  } catch {
    return fallbackTarget;
  }
}
