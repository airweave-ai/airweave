import { Outlet, createFileRoute } from '@tanstack/react-router';
import { AuthProvidersPage } from '@/app/pages/auth-providers';
import {
  ensureListAuthProviderConnections,
  ensureListAuthProviders,
} from '@/features/auth-providers';

export const Route = createFileRoute('/_authenticated/_app/auth-providers')({
  loader: ({ context }) =>
    Promise.all([
      ensureListAuthProviderConnections({
        queryClient: context.queryClient,
        organizationId: context.currentOrganizationId,
      }),
      ensureListAuthProviders({
        queryClient: context.queryClient,
        organizationId: context.currentOrganizationId,
      }),
    ]),
  component: RouteComponent,
  staticData: {
    breadcrumb: 'Auth Providers',
  },
});

function RouteComponent() {
  return (
    <>
      <AuthProvidersPage />
      <Outlet />
    </>
  );
}
