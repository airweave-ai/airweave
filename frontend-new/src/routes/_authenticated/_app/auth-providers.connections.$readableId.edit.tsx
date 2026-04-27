import { createFileRoute } from '@tanstack/react-router';
import { AuthProviderConnectionEditPage } from '@/app/pages/auth-providers/edit-connection-page';
import { prefetchAuthProviderConnection } from '@/features/auth-providers';

export const Route = createFileRoute(
  '/_authenticated/_app/auth-providers/connections/$readableId/edit',
)({
  loader: ({ context, params }) =>
    prefetchAuthProviderConnection({
      organizationId: context.currentOrganizationId,
      queryClient: context.queryClient,
      readableId: params.readableId,
    }),
  component: RouteComponent,
});

function RouteComponent() {
  return <AuthProviderConnectionEditPage />;
}
