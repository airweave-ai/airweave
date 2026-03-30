import { createFileRoute, redirect } from '@tanstack/react-router';
import {
  AuthCallbackPage,
  callbackSearchSchema,
} from '@/app/pages/auth/callback';
import { ensureCurrentUser } from '@/features/app-session';
import { getSafeRedirectTarget } from '@/shared/auth';

export const Route = createFileRoute('/callback')({
  pendingComponent: CallbackPendingComponent,
  pendingMs: 0,
  beforeLoad: async ({ context, search }) => {
    const redirectTarget = getSafeRedirectTarget({
      fallbackTarget: '/',
      redirectTarget: search.redirect,
    });

    if (context.auth.status !== 'authenticated') {
      throw redirect({
        search: {
          redirect: search.redirect,
          organization_name: search.organization_name,
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
  validateSearch: callbackSearchSchema,
});

function CallbackPendingComponent() {
  const search = Route.useSearch();

  return <AuthCallbackPage organizationName={search.organization_name} />;
}
