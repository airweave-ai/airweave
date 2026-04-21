import { createFileRoute } from '@tanstack/react-router';
import { ApiKeysCreatePage } from '@/app/pages/api-keys/create-page';

export const Route = createFileRoute('/_authenticated/_app/api-keys/create')({
  component: RouteComponent,
});

function RouteComponent() {
  return <ApiKeysCreatePage />;
}
