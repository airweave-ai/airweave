import type { CreateClientConfig } from './generated/client.gen';
import { getAuthBridgeSnapshot } from '@/shared/auth/auth-bridge';
import { env } from '@/shared/config/env';

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  auth: async () => {
    const authBridgeSnapshot = getAuthBridgeSnapshot();

    if (authBridgeSnapshot.isLoading || !authBridgeSnapshot.isAuthenticated) {
      return undefined;
    }

    return (await authBridgeSnapshot.getAccessToken()) ?? undefined;
  },
  baseUrl: env.VITE_API_URL,
});
