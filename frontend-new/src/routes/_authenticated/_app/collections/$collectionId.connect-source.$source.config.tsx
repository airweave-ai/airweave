import { createFileRoute } from '@tanstack/react-router';
import { ConnectSourceConfigPage } from '@/app/pages/collections/connect-source/config-page';

export const Route = createFileRoute(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/config',
)({
  component: ConnectSourceConfigPage,
});
