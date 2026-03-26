import { createFileRoute } from '@tanstack/react-router';
import { DashboardPage } from '@/app/pages/dashboard';

export const Route = createFileRoute('/_authenticated/_app/')({
  component: RouteComponent,
});

function RouteComponent() {
  return <DashboardPage />;
}
