import { createFileRoute } from '@tanstack/react-router';
import { DashboardPage } from '@/app/pages/dashboard';
import {
  ensureListCollections,
  prefetchCollectionCount,
} from '@/features/collections';

export const Route = createFileRoute('/_authenticated/_app/')({
  loader: async ({ context }) => {
    const collectionListPromise = ensureListCollections({
      queryClient: context.queryClient,
      organizationId: context.currentOrganizationId,
    });

    void prefetchCollectionCount({
      queryClient: context.queryClient,
      organizationId: context.currentOrganizationId,
    });

    await collectionListPromise;
  },
  component: RouteComponent,
});

function RouteComponent() {
  return <DashboardPage />;
}
