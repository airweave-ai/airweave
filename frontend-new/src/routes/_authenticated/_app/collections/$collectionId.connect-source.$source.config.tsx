import { createFileRoute } from '@tanstack/react-router';
import { ConnectSourceConfigPage } from '@/app/pages/collections/connect-source/config-page';
import {
  ensureListAuthProviderConnections,
  ensureListAuthProviders,
} from '@/features/auth-providers';
import { ensureSource } from '@/features/source-connections';

export const Route = createFileRoute(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/config',
)({
  loader: ({ context, params }) =>
    Promise.all([
      ensureSource({
        queryClient: context.queryClient,
        organizationId: context.currentOrganizationId,
        sourceShortName: params.source,
      }),
      ensureListAuthProviders({
        queryClient: context.queryClient,
        organizationId: context.currentOrganizationId,
      }),
      ensureListAuthProviderConnections({
        queryClient: context.queryClient,
        organizationId: context.currentOrganizationId,
      }),
    ]),
  component: ConnectSourceConfigPage,
});
