import { Outlet, createFileRoute, redirect } from '@tanstack/react-router';
import { AppShell } from '@/app/layouts/app-shell';
import { AppSessionProvider, ensureAppSession } from '@/features/app-session';
import { setCurrentRequestContext } from '@/shared/api/request-context';

export const Route = createFileRoute('/_authenticated/_app')({
  loader: async ({ context }) => {
    const result = await ensureAppSession(context);

    if (result.error) {
      throw redirect({ to: '/onboarding' });
    }

    setCurrentRequestContext({
      organizationId: result.data.currentOrganizationId,
    });

    return result.data;
  },
  component: LayoutComponent,
});

function LayoutComponent() {
  return (
    <AppSessionProvider>
      <AppShell>
        <Outlet />
      </AppShell>
    </AppSessionProvider>
  );
}
