import { createFileRoute } from '@tanstack/react-router';
import { AuthProviderConnectPage } from '@/app/pages/auth-providers/connect-page';
import { prefetchAuthProviderDetail } from '@/features/auth-providers';

export const Route = createFileRoute(
  '/_authenticated/_app/auth-providers/$shortName/connect',
)({
  loader: ({ context, params }) =>
    prefetchAuthProviderDetail({
      organizationId: context.currentOrganizationId,
      queryClient: context.queryClient,
      shortName: params.shortName,
    }),
  component: RouteComponent,
});

function RouteComponent() {
  return <AuthProviderConnectPage />;
}
