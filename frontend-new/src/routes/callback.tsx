import * as z from 'zod';
import { createFileRoute, redirect } from '@tanstack/react-router';
import { AuthCallbackPage } from '@/app/pages/auth-callback';
import { ensureCurrentUser } from '@/features/app-session';

const callbackSearchSchema = z.object({
  redirect: z.string().optional(),
});

export const Route = createFileRoute('/callback')({
  loaderDeps: ({ search: { redirect: redirectSearchParam } }) => ({
    redirectSearchParam,
  }),
  loader: async ({ context, deps }) => {
    const redirectTarget = getSafeRedirectTarget(deps.redirectSearchParam);

    if (context.auth.status !== 'authenticated') {
      throw redirect({
        search: {
          redirect: redirectTarget,
        },
        to: '/login',
      });
    }

    await ensureCurrentUser({
      authUser: context.auth.user,
      queryClient: context.queryClient,
    });

    throw redirect({ to: redirectTarget });
  },
  pendingComponent: AuthCallbackPage,
  validateSearch: callbackSearchSchema,
});

function getSafeRedirectTarget(redirectTarget?: string) {
  if (!redirectTarget) {
    return '/';
  }

  if (redirectTarget.startsWith('/')) {
    return redirectTarget;
  }

  try {
    const targetUrl = new URL(redirectTarget, window.location.origin);

    if (targetUrl.origin !== window.location.origin) {
      return '/';
    }

    return `${targetUrl.pathname}${targetUrl.search}${targetUrl.hash}`;
  } catch {
    return '/';
  }
}
