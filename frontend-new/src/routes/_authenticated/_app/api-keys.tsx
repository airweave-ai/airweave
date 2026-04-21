import { Outlet, createFileRoute } from '@tanstack/react-router';
import { ApiKeysPage } from '@/app/pages/api-keys';
import { ensureListApiKeys } from '@/features/api-keys';

export const Route = createFileRoute('/_authenticated/_app/api-keys')({
  loader: ({ context }) =>
    ensureListApiKeys({
      queryClient: context.queryClient,
      organizationId: context.currentOrganizationId,
    }),
  component: RouteComponent,
  staticData: {
    breadcrumb: 'API Keys',
  },
});

function RouteComponent() {
  return (
    <>
      <ApiKeysPage />
      <Outlet />
    </>
  );
}
