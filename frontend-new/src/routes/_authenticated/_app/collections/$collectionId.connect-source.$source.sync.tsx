import { createFileRoute } from '@tanstack/react-router';
import { ConnectSourceSyncPage } from '@/app/pages/collections/connect-source/sync-page';
import { connectSourceSyncSearchSchema } from '@/app/pages/collections/connect-source/search';

export const Route = createFileRoute(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/sync',
)({
  validateSearch: connectSourceSyncSearchSchema,
  component: ConnectSourceSyncPage,
});
