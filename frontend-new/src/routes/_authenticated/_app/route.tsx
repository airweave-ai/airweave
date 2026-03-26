import { Outlet, createFileRoute } from '@tanstack/react-router';
import { AppShell } from '@/app/layouts/app-shell';

export const Route = createFileRoute('/_authenticated/_app')({
  component: LayoutComponent,
});

function LayoutComponent() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
