import { Outlet, createFileRoute } from '@tanstack/react-router';
import { AppSidebar } from '@/components/app-sidebar';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';

export const Route = createFileRoute('/_app')({
  component: LayoutComponent,
});

function LayoutComponent() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="p-3">
        <Outlet />
      </SidebarInset>
    </SidebarProvider>
  );
}
