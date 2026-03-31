import { CollectionsPage } from '@/app/pages/collections';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/_authenticated/_app/collections')({
  component: RouteComponent,
});

function RouteComponent() {
  return <CollectionsPage />;
}
