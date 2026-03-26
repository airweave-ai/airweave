import { getCurrentRequestContext } from './request-context';
import type { RequestContext } from './request-context';

interface OptionsWithHeaders {
  headers?: HeadersInit;
}

function getRequestContextHeaders(requestContext: RequestContext) {
  const headers: Record<string, string> = {};

  if (requestContext.organizationId) {
    headers['X-Organization-ID'] = requestContext.organizationId;
  }

  return headers;
}

function normalizeHeaders(headers?: HeadersInit) {
  return Object.fromEntries(new Headers(headers).entries());
}

export function withRequestContext<T extends OptionsWithHeaders>(
  options: T | undefined,
  requestContext: RequestContext,
) {
  const headers = {
    ...normalizeHeaders(options?.headers),
    ...getRequestContextHeaders(requestContext),
  };

  if (Object.keys(headers).length === 0) {
    return { ...(options ?? {}) } as T;
  }

  return {
    ...(options ?? {}),
    headers,
  } as T;
}

export function withCurrentRequestContext<T extends OptionsWithHeaders>(
  options?: T,
) {
  return withRequestContext(options, getCurrentRequestContext());
}
