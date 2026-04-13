import { createFileRoute, redirect } from '@tanstack/react-router';
import { ConnectSourceSyncPage } from '@/app/pages/collections/connect-source/sync-page';
import { connectSourceSyncSearchSchema } from '@/app/pages/collections/connect-source/search';
import {
  ensureSource,
  ensureSourceConnection,
} from '@/features/source-connections';

export const Route = createFileRoute(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/sync',
)({
  loaderDeps: ({ search }) => ({
    sourceConnectionId: search.source_connection_id,
  }),
  loader: async ({ context, deps, params }) => {
    const [, sourceConnection] = await Promise.all([
      ensureSource({
        organizationId: context.currentOrganizationId,
        queryClient: context.queryClient,
        sourceShortName: params.source,
      }),
      ensureSourceConnection({
        organizationId: context.currentOrganizationId,
        queryClient: context.queryClient,
        sourceConnectionId: deps.sourceConnectionId,
      }),
    ]);

    if (
      sourceConnection.readable_collection_id !== params.collectionId ||
      sourceConnection.short_name !== params.source
    ) {
      throw redirect({
        params: { collectionId: params.collectionId },
        replace: true,
        to: '/collections/$collectionId',
      });
    }

    if (!sourceConnection.auth.authenticated) {
      throw redirect({
        params: {
          collectionId: params.collectionId,
          source: params.source,
        },
        replace: true,
        search: {
          source_connection_id: deps.sourceConnectionId,
        },
        to: '/collections/$collectionId/connect-source/$source/auth',
      });
    }

    return {
      sourceConnectionId: deps.sourceConnectionId,
    };
  },
  validateSearch: connectSourceSyncSearchSchema,
  component: ConnectSourceSyncPage,
});
