import { ApiKeysCreatePage } from '@/app/pages/api-keys/create-page';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/_authenticated/_app/api-keys/create')({
  component: RouteComponent,
});

function RouteComponent() {
  return <ApiKeysCreatePage />;
}
