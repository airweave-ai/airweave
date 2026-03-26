import type { CreateClientConfig } from './generated/client.gen';
import { getAuthStoreSnapshot } from '@/shared/auth/auth-store';
import { env } from '@/shared/config/env';

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  auth: async () => {
    const authStoreSnapshot = getAuthStoreSnapshot();

    if (authStoreSnapshot.isLoading || !authStoreSnapshot.isAuthenticated) {
      return undefined;
    }

    return (await authStoreSnapshot.getAccessToken()) ?? undefined;
  },
  baseUrl: env.VITE_API_URL,
});
