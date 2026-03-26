import type { QueryClient } from '@tanstack/react-query';
import type { AuthState } from '@/shared/auth';

export interface RouterContext {
  auth: AuthState;
  queryClient: QueryClient;
}
