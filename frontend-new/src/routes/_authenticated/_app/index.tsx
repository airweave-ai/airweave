import { createFileRoute } from '@tanstack/react-router';
import { DashboardPage } from '@/app/pages/dashboard';
import {
  ensureCollectionCount,
  ensureListCollections,
} from '@/features/collections';

export const Route = createFileRoute('/_authenticated/_app/')({
  loader: ({ context }) =>
    Promise.all([
      ensureCollectionCount({
        queryClient: context.queryClient,
        organizationId: context.currentOrganizationId,
      }),
      ensureListCollections({
        queryClient: context.queryClient,
        organizationId: context.currentOrganizationId,
      }),
    ]),
  component: RouteComponent,
});

function RouteComponent() {
  return <DashboardPage />;
}
