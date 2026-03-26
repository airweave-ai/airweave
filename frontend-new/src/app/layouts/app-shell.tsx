import type { PropsWithChildren } from 'react';
import { AppSidebar } from '@/app/layouts/app-sidebar';
import { SidebarInset, SidebarProvider } from '@/shared/ui/sidebar';

export function AppShell({ children }: PropsWithChildren) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="p-3">{children}</SidebarInset>
    </SidebarProvider>
  );
}
