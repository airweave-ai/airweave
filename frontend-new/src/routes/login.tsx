import { createFileRoute, redirect } from '@tanstack/react-router';
import { LoginPage, loginSearchSchema } from '@/app/pages/auth/login';
import { getSafeRedirectTarget } from '@/shared/auth';

export const Route = createFileRoute('/login')({
  component: LoginRouteComponent,
  pendingComponent: LoginPendingComponent,
  pendingMs: 0,
  preload: false,
  beforeLoad: async ({ context, search }) => {
    const redirectTarget = getSafeRedirectTarget({
      fallbackTarget: '/',
      redirectTarget: search.redirect,
    });

    if (context.auth.status === 'authenticated') {
      throw redirect({ to: redirectTarget });
    }

    await context.auth.login({
      invitation: search.invitation,
      organization: search.organization,
      organizationName: search.organization_name,
      returnTo: redirectTarget,
    });
  },
  validateSearch: loginSearchSchema,
});

function LoginRouteComponent() {
  const search = Route.useSearch();

  return <LoginPage organizationName={search.organization_name} />;
}

function LoginPendingComponent() {
  return <LoginRouteComponent />;
}
