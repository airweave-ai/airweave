import * as React from 'react';
import { Outlet, createFileRoute, redirect } from '@tanstack/react-router';
import { appSearchSchema } from '@/app/layouts/app-search';
import { AppShell } from '@/app/layouts/app-shell';
import { AppSessionProvider } from '@/app/providers/app-session-provider';
import { ensureAppSession } from '@/features/app-session';
import { AirweaveLoader } from '@/shared/components/airweave-loader';

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
  validateSearch: appSearchSchema,
  component: LayoutComponent,
});

function LayoutComponent() {
  return (
    <AppSessionProvider>
      <AppShell>
        <React.Suspense fallback={<AirweaveLoader />}>
          <Outlet />
        </React.Suspense>
      </AppShell>
    </AppSessionProvider>
  );
}
