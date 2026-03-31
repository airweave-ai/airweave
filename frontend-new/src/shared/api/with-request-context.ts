import { getCurrentRequestContext } from './request-context';
import type { RequestContext } from './request-context';

interface OptionsWithHeaders {
  headers?: RequestInit['headers'] | Record<string, unknown>;
}

function getRequestContextHeaders(requestContext: RequestContext) {
  const headers: Record<string, string> = {};

  if (requestContext.organizationId) {
    headers['X-Organization-ID'] = requestContext.organizationId;
  }

  return headers;
}

function normalizeHeaders(headers?: OptionsWithHeaders['headers']) {
  if (!headers) {
    return {};
  }

  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }

  if (Array.isArray(headers)) {
    return Object.fromEntries(
      headers.map(([key, value]) => [key, String(value)]),
    );
  }

  return Object.fromEntries(
    Object.entries(headers).flatMap(([key, value]) => {
      if (value == null) {
        return [];
      }

      if (Array.isArray(value)) {
        return [[key, value.map((item) => String(item)).join(', ')]];
      }

      return [[key, String(value)]];
    }),
  );
}

export function withRequestContext<T extends OptionsWithHeaders>(
  requestContext: RequestContext,
  options: T | undefined = undefined,
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
  return withRequestContext(getCurrentRequestContext(), options);
}
