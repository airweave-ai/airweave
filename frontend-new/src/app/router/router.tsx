import { createRouter as createTanStackRouter } from '@tanstack/react-router';
import type { RouterContext } from './context';
import { routeTree } from '@/routeTree.gen';
import { queryClient } from '@/shared/api';

export const router = createTanStackRouter({
  routeTree,
  context: {
    auth: undefined as unknown as RouterContext['auth'],
    queryClient,
  },
  scrollRestoration: true,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
