import { createFileRoute } from '@tanstack/react-router';
import { DashboardPage } from '@/app/pages/dashboard';
import {
  ensureListCollections,
  ensureCollectionCount,
} from '@/features/collections';

export const Route = createFileRoute('/_authenticated/_app/')({
  loader: ({ context }) =>
    Promise.all([
      ensureListCollections({
        queryClient: context.queryClient,
        organizationId: context.currentOrganizationId,
      }),
      ensureCollectionCount({
        queryClient: context.queryClient,
        organizationId: context.currentOrganizationId,
      }),
    ]),
  component: RouteComponent,
});

function RouteComponent() {
  return <DashboardPage />;
}
