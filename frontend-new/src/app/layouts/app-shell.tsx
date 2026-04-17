import { AppDialog } from './app-dialog';
import { AppHeader } from './app-header';
import { AppSidebar } from './app-sidebar';
import type { PropsWithChildren } from 'react';
import { SidebarInset, SidebarProvider } from '@/shared/ui/sidebar';

export function AppShell({ children }: PropsWithChildren) {
  return (
    <SidebarProvider className="h-svh overflow-hidden">
      <AppSidebar />
      <SidebarInset className="min-h-0 overflow-hidden">
        <AppHeader />
        <div className="flex min-h-0 flex-1 flex-col overflow-auto">
          {children}
        </div>
        <AppDialog />
      </SidebarInset>
    </SidebarProvider>
  );
}
