import { createFileRoute, redirect } from '@tanstack/react-router';
import {
  ConnectSourceAuthErrorPage,
  ConnectSourceAuthPage,
} from '@/app/pages/collections/connect-source/auth-page';
import { connectSourceAuthSearchSchema } from '@/app/pages/collections/connect-source/search';
import {
  ensureSourceConnection,
  isBrowserOAuthMethod,
} from '@/features/source-connections';

export const Route = createFileRoute(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/auth',
)({
  beforeLoad: ({ params, search }) => {
    if (search.source_connection_id) {
      return;
    }

    throw redirect({
      params: { collectionId: params.collectionId },
      replace: true,
      to: '/collections/$collectionId',
    });
  },
  loaderDeps: ({ search }) => ({
    callbackStatus: search.status,
    sourceConnectionId: search.source_connection_id,
  }),
  loader: async ({ context, deps, params }) => {
    if (!deps.sourceConnectionId) {
      throw redirect({
        params: { collectionId: params.collectionId },
        replace: true,
        to: '/collections/$collectionId',
      });
    }

    const sourceConnection = await ensureSourceConnection({
      organizationId: context.currentOrganizationId,
      queryClient: context.queryClient,
      sourceConnectionId: deps.sourceConnectionId,
    });

    if (
      !isBrowserOAuthMethod(sourceConnection.auth.method) ||
      sourceConnection.readable_collection_id !== params.collectionId ||
      sourceConnection.short_name !== params.source
    ) {
      throw redirect({
        params: { collectionId: params.collectionId },
        replace: true,
        to: '/collections/$collectionId',
      });
    }

    const isCallbackReturn = deps.callbackStatus === 'success';
    const requiresAuth =
      sourceConnection.status === 'pending_auth' ||
      sourceConnection.status === 'needs_reauth' ||
      isCallbackReturn;

    if (sourceConnection.auth.authenticated && !requiresAuth) {
      throw redirect({
        params: {
          collectionId: params.collectionId,
          source: params.source,
        },
        replace: true,
        search: {
          source_connection_id: deps.sourceConnectionId,
        },
        to: '/collections/$collectionId/connect-source/$source/sync',
      });
    }

    return {
      sourceConnectionId: deps.sourceConnectionId,
    };
  },
  validateSearch: connectSourceAuthSearchSchema,
  component: ConnectSourceAuthPage,
  errorComponent: ConnectSourceAuthErrorPage,
});
