import { AppDialog } from './app-dialog';
import type { PropsWithChildren } from 'react';
import { AppHeader } from '@/app/layouts/app-header';
import { AppSidebar } from '@/app/layouts/app-sidebar';
import { SidebarInset, SidebarProvider } from '@/shared/ui/sidebar';

export function AppShell({ children }: PropsWithChildren) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="overflow-hidden">
        <AppHeader />
        <div className="flex-1 overflow-auto">{children}</div>
        <AppDialog />
      </SidebarInset>
    </SidebarProvider>
  );
}
