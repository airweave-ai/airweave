import { CollectionsPage } from '@/app/pages/collections';
import { ensureListCollections } from '@/features/collections';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/_authenticated/_app/collections')({
  component: RouteComponent,
  loader: ({ context }) => ensureListCollections(context),
});

function RouteComponent() {
  return <CollectionsPage />;
}
