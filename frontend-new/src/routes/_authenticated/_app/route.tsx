import { Outlet, createFileRoute, redirect } from '@tanstack/react-router';
import { AppShell } from '@/app/layouts/app-shell';
import { AppSessionProvider } from '@/app/providers/app-session-provider';
import { ensureAppSession } from '@/features/app-session';

export const Route = createFileRoute('/_authenticated/_app')({
  beforeLoad: async ({ context }) => {
    const result = await ensureAppSession(context);

    if (result.error) {
      throw redirect({ to: '/onboarding' });
    }

    return {
      currentOrganizationId: result.data.currentOrganizationId,
    };
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
