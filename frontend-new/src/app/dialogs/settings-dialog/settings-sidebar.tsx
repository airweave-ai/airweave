import { IconArrowUp, IconChartBar, IconUsers } from '@tabler/icons-react';
import type { Icon } from '@tabler/icons-react';

import type { SettingsPage } from '@/app/layouts/app-search';
import type * as React from 'react';
import { SettingsLink } from '@/app/components/settings-link';
import { UserAvatar } from '@/shared/components/user-avatar';
import { useAppSession } from '@/shared/session';
import { Button } from '@/shared/ui/button';
import { cn } from '@/shared/tailwind/cn';

type SettingsItem = {
  page: SettingsPage;
  label: string;
  icon: Icon;
};

const organizationItems: Array<SettingsItem> = [
  { page: 'people', label: 'People', icon: IconUsers },
  { page: 'usage', label: 'Usage', icon: IconChartBar },
];

function SettingsSidebar({ page: activePage }: { page: SettingsPage }) {
  const { viewer } = useAppSession();
  const viewerLabel = viewer.name ?? viewer.email;

  return (
    <aside className="flex min-h-0 flex-col gap-4 border-b bg-sidebar p-4 text-sidebar-foreground md:border-r md:border-b-0">
      <SettingsGroup label="Account">
        <SettingsNavButton page="account" activePage={activePage}>
          <UserAvatar
            email={viewer.email}
            name={viewer.name}
            picture={viewer.picture}
            className="size-5"
          />
          <SettingsNavItemLabel>{viewerLabel}</SettingsNavItemLabel>
        </SettingsNavButton>
      </SettingsGroup>

      <SettingsGroup label="Organization">
        {organizationItems.map((item) => (
          <SettingsNavButton
            key={item.page}
            page={item.page}
            activePage={activePage}
          >
            <SettingsNavItemIconBox>
              <item.icon className="size-3.5" />
            </SettingsNavItemIconBox>
            <SettingsNavItemLabel>{item.label}</SettingsNavItemLabel>
          </SettingsNavButton>
        ))}
      </SettingsGroup>

      <SettingsGroup label="Access & Billing">
        <SettingsNavButton page="billing" activePage={activePage}>
          <SettingsNavItemIconBox className="border-blue-400 bg-blue-900">
            <IconArrowUp className="size-3.5 text-blue-300" />
          </SettingsNavItemIconBox>
          <SettingsNavItemLabel className="text-blue-400">
            Upgrade Plan
          </SettingsNavItemLabel>
        </SettingsNavButton>
      </SettingsGroup>
    </aside>
  );
}

function SettingsGroup({
  children,
  label,
}: React.PropsWithChildren<{
  label: string;
}>) {
  return (
    <div className="space-y-2">
      <p className="truncate font-mono text-xs leading-5 text-muted-foreground">
        {label}
      </p>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function SettingsNavItemIconBox({
  className,
  ...props
}: React.PropsWithChildren<{ className?: string }>) {
  return (
    <span
      className={cn(
        'flex size-5 shrink-0 items-center justify-center rounded-sm border border-sidebar-border',
        className,
      )}
      {...props}
    />
  );
}

function SettingsNavItemLabel({
  className,
  ...props
}: React.PropsWithChildren<{ className?: string }>) {
  return (
    <span
      className={cn('min-w-0 flex-1 truncate text-left font-normal', className)}
      {...props}
    />
  );
}

function SettingsNavButton({
  activePage,
  page,
  children,
}: React.PropsWithChildren<{
  page: SettingsPage;
  activePage: SettingsPage;
}>) {
  return (
    <Button
      type="button"
      variant="ghost"
      className="w-full justify-start gap-2 px-2 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground"
      data-active={activePage === page ? 'true' : undefined}
      asChild
    >
      <SettingsLink page={page} replace>
        {children}
      </SettingsLink>
    </Button>
  );
}

export { SettingsSidebar };
