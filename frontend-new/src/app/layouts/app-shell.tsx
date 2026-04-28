import * as React from 'react';
import { AppDialog } from './app-dialog';
import { AppHeader } from './app-header';
import { AppSidebar } from './app-sidebar';
import type { PropsWithChildren } from 'react';
import type { Organization } from '@/shared/api';
import { router } from '@/app/router/router';
import { setPreferredOrganizationId } from '@/features/app-session';
import { CreateOrganizationDialog } from '@/features/organizations';
import { SidebarInset, SidebarProvider } from '@/shared/ui/sidebar';

export function AppShell({ children }: PropsWithChildren) {
  const [createOrganizationOpen, setCreateOrganizationOpen] =
    React.useState(false);

  const handleOrganizationCreated = React.useCallback(
    async (organization: Organization) => {
      setPreferredOrganizationId(organization.id);
      await router.navigate({ to: '/' });
      await router.invalidate({ sync: true });
    },
    [],
  );

  return (
    <SidebarProvider className="h-svh overflow-hidden">
      <CreateOrganizationDialog
        onCreated={handleOrganizationCreated}
        onOpenChange={setCreateOrganizationOpen}
        open={createOrganizationOpen}
      />
      <AppSidebar
        onCreateOrganization={() => setCreateOrganizationOpen(true)}
      />
      <SidebarInset className="min-h-0 overflow-hidden">
        <AppHeader
          onCreateOrganization={() => setCreateOrganizationOpen(true)}
        />
        <div className="flex min-h-0 flex-1 flex-col overflow-auto">
          {children}
        </div>
        <AppDialog />
      </SidebarInset>
    </SidebarProvider>
  );
}
