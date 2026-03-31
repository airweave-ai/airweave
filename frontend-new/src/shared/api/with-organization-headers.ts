import type { OrganizationScope } from './organization-scope';

interface OptionsWithHeaders {
  headers?: RequestInit['headers'] | Record<string, unknown>;
}

function getOrganizationHeaders(organizationScope: OrganizationScope) {
  const headers: Record<string, string> = {};

  if (organizationScope.organizationId) {
    headers['X-Organization-ID'] = organizationScope.organizationId;
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

export function withOrganizationHeaders<T extends OptionsWithHeaders>(
  organizationScope: OrganizationScope,
  options: T | undefined = undefined,
) {
  const headers = {
    ...normalizeHeaders(options?.headers),
    ...getOrganizationHeaders(organizationScope),
  };

  if (Object.keys(headers).length === 0) {
    return { ...(options ?? {}) } as T;
  }

  return {
    ...(options ?? {}),
    headers,
  } as T;
}
