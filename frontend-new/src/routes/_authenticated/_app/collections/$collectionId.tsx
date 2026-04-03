import { createFileRoute } from '@tanstack/react-router';
import type { Collection } from '@/shared/api';
import { CollectionDetailPage } from '@/app/pages/collections/detail-page';
import { ensureCollection } from '@/features/collections';

export const Route = createFileRoute(
  '/_authenticated/_app/collections/$collectionId',
)({
  loader: ({ context, params }) =>
    ensureCollection({
      collectionId: params.collectionId,
      queryClient: context.queryClient,
      organizationId: context.currentOrganizationId,
    }),
  staticData: {
    breadcrumb: ({ loaderData }) => (loaderData as Collection).name,
  },
  component: RouteComponent,
});

function RouteComponent() {
  const { collectionId } = Route.useParams();

  return <CollectionDetailPage collectionId={collectionId} />;
}
