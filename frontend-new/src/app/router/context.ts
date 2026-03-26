import type { QueryClient } from '@tanstack/react-query';
import type { AuthResolvedState } from '@/shared/auth';

export interface RouterContext {
  auth: AuthResolvedState;
  queryClient: QueryClient;
}
