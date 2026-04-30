import { Outlet, createFileRoute } from '@tanstack/react-router';
import type { Collection } from '@/shared/api';
import { CollectionDetailPage } from '@/app/pages/collections/detail';
import { ensureCollection } from '@/features/collections';
import { ensureListSourceConnections } from '@/features/source-connections';
import { AirweaveLoader } from '@/shared/components/airweave-loader';

export const Route = createFileRoute(
  '/_authenticated/_app/collections/$collectionId',
)({
  loader: async ({ context, params }) => {
    const [collection] = await Promise.all([
      ensureCollection({
        collectionId: params.collectionId,
        queryClient: context.queryClient,
        organizationId: context.currentOrganizationId,
      }),
      ensureListSourceConnections({
        collectionId: params.collectionId,
        queryClient: context.queryClient,
        organizationId: context.currentOrganizationId,
      }),
    ]);

    return collection;
  },
  staticData: {
    breadcrumb: ({ loaderData }) =>
      (loaderData as Collection | undefined)?.name,
  },
  pendingComponent: PendingComponent,
  component: RouteComponent,
});

function PendingComponent() {
  return <AirweaveLoader>Loading collection...</AirweaveLoader>;
}

function RouteComponent() {
  const { collectionId } = Route.useParams();

  return (
    <>
      <CollectionDetailPage collectionId={collectionId} />
      <Outlet />
    </>
  );
}
