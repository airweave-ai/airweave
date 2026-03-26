import type { CreateClientConfig } from './generated/client.gen';
import { getAuthBridgeSnapshot } from '@/shared/auth/auth-bridge';
import { env } from '@/shared/config/env';

function mergeHeaders(...headerSets: Array<HeadersInit | undefined>) {
  const headers = new Headers();

  for (const headerSet of headerSets) {
    if (!headerSet) {
      continue;
    }

    const currentHeaders = new Headers(headerSet);
    currentHeaders.forEach((value, key) => {
      headers.set(key, value);
    });
  }

  return headers;
}

// TODO: Add 'X-Organization-ID' and 'X-Airweave-Session-ID' headers
const airweaveFetch: typeof fetch = async (input, init) => {
  const authBridgeSnapshot = getAuthBridgeSnapshot();
  let accessToken: string | null = null;

  if (authBridgeSnapshot.isAuthenticated) {
    accessToken = await authBridgeSnapshot.getAccessToken();
  }

  const requestHeaders = input instanceof Request ? input.headers : undefined;
  const headers = mergeHeaders(requestHeaders, init?.headers);

  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  if (input instanceof Request) {
    return fetch(new Request(input, { ...init, headers }));
  }

  return fetch(input, { ...init, headers });
};

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: env.VITE_API_URL,
  fetch: airweaveFetch,
});
