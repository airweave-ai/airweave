import { createFileRoute } from '@tanstack/react-router';
import { ConnectSourcePickerPage } from '@/app/pages/collections/connect-source/picker-page';
import { prefetchSources } from '@/features/source-connections';

export const Route = createFileRoute(
  '/_authenticated/_app/collections/$collectionId/connect-source/',
)({
  loader: ({ context }) =>
    prefetchSources({
      organizationId: context.currentOrganizationId,
      queryClient: context.queryClient,
    }),
  component: ConnectSourcePickerPage,
});
