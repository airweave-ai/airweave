import { createFileRoute } from '@tanstack/react-router';
import { ConnectSourceAuthPage } from '@/app/pages/collections/connect-source/auth-page';
import { connectSourceAuthSearchSchema } from '@/app/pages/collections/connect-source/search';
import { prefetchSourceConnection } from '@/features/source-connections';

export const Route = createFileRoute(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/auth',
)({
  loaderDeps: ({ search }) => ({
    sourceConnectionId: search.source_connection_id,
  }),
  loader: async ({ context, deps }) => {
    if (!deps.sourceConnectionId) {
      return;
    }

    await prefetchSourceConnection({
      organizationId: context.currentOrganizationId,
      queryClient: context.queryClient,
      sourceConnectionId: deps.sourceConnectionId,
    });
  },
  validateSearch: connectSourceAuthSearchSchema,
  component: ConnectSourceAuthPage,
});
