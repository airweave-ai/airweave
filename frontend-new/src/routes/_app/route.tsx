import { AppSidebar } from '@/components/app-sidebar';
import { SidebarProvider } from '@/components/ui/sidebar';
import { createFileRoute, Outlet } from '@tanstack/react-router';

export const Route = createFileRoute('/_app')({
  component: LayoutComponent,
});

function LayoutComponent() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <main>
        <Outlet />
      </main>
    </SidebarProvider>
  );
}
