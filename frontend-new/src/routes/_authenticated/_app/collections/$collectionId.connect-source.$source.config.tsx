import { createFileRoute } from '@tanstack/react-router';
import { ConnectSourceConfigPage } from '@/app/pages/collections/connect-source/config-page';
import { ensureSource } from '@/features/source-connections';

export const Route = createFileRoute(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/config',
)({
  loader: ({ context, params }) =>
    ensureSource({
      queryClient: context.queryClient,
      organizationId: context.currentOrganizationId,
      sourceShortName: params.source,
    }),
  component: ConnectSourceConfigPage,
});
