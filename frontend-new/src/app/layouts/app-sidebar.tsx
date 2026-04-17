import {
  AppWindow,
  ChevronDown,
  CreditCard,
  EllipsisVertical,
  Home,
  LineChart,
  LogOut,
  Plus,
  Settings,
  Users,
} from 'lucide-react';
import { Link, useMatchRoute } from '@tanstack/react-router';
import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { CreateCollectionButton } from '@/app/components/create-collection-button';
import { useAuth } from '@/shared/auth';
import { UserAvatar } from '@/shared/components/user-avatar';
import { useAppSession } from '@/shared/session';
import {
  OrganizationSwitcher,
  OrganizationSwitcherMenu,
  OrganizationSwitcherTrigger,
} from '@/features/organizations';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';
import { LogoMark } from '@/shared/ui/logo-mark';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from '@/shared/ui/sidebar';

type NavigationItem = {
  label: string;
  icon: LucideIcon;
  to: string;
  fuzzy?: boolean;
};

const navigationItems: Array<NavigationItem> = [
  { label: 'Dashboard', icon: Home, to: '/' },
  { label: 'Collections', icon: AppWindow, to: '/collections', fuzzy: true },
];

function SidebarIconFrame({ children }: { children: ReactNode }) {
  return (
    <span className="flex size-5 shrink-0 items-center justify-center rounded-[0.35rem] border border-sidebar-border">
      {children}
    </span>
  );
}

export function AppSidebar() {
  const auth = useAuth();
  const matchRoute = useMatchRoute();
  const {
    currentOrganization,
    currentOrganizationId,
    organizations,
    setCurrentOrganizationId,
    viewer,
  } = useAppSession();
  const viewerLabel = viewer.name ?? viewer.email;

  return (
    <Sidebar variant="inset">
      <SidebarHeader>
        <div className="flex min-w-0 items-center gap-2">
          <div className="min-w-0 flex-1">
            <OrganizationSwitcher>
              <OrganizationSwitcherTrigger asChild>
                <SidebarMenuButton
                  className="w-full min-w-0 gap-2 font-semibold data-[state=open]:[&_svg[data-role=indicator]]:rotate-180"
                  type="button"
                >
                  <LogoMark />
                  <span className="min-w-0 flex-1 truncate">
                    {currentOrganization.name}
                  </span>
                  <ChevronDown
                    className="size-4 shrink-0 text-sidebar-foreground/50 transition-[rotate]"
                    data-role="indicator"
                  />
                </SidebarMenuButton>
              </OrganizationSwitcherTrigger>
              <OrganizationSwitcherMenu
                className="min-w-79"
                currentOrganizationId={currentOrganizationId}
                onCurrentOrganizationChange={setCurrentOrganizationId}
                organizations={organizations}
              />
            </OrganizationSwitcher>
          </div>

          <div className="flex flex-none items-center gap-1">
            <SidebarMenuButton
              className="size-7 flex-none justify-center p-0 text-sidebar-foreground/50"
              type="button"
            >
              <Settings className="size-3.5" />
              <span className="sr-only">Open settings</span>
            </SidebarMenuButton>

            <SidebarTrigger className="text-sidebar-foreground/50" />
          </div>
        </div>

        <CreateCollectionButton variant="secondary" data-icon="inline-start">
          <Plus />
          Create Collection
        </CreateCollectionButton>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1.5">
              {navigationItems.map((item) => {
                const Icon = item.icon;

                return (
                  <SidebarMenuItem key={item.label}>
                    <SidebarMenuButton
                      asChild
                      isActive={
                        !!matchRoute({
                          to: item.to,
                          fuzzy: item.fuzzy,
                        })
                      }
                    >
                      <Link to={item.to}>
                        <SidebarIconFrame>
                          <Icon className="!size-3.5" />
                        </SidebarIconFrame>
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  className="gap-3 data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                  size="lg"
                  type="button"
                >
                  <UserAvatar
                    email={viewer.email}
                    name={viewer.name}
                    picture={viewer.picture}
                  />
                  <span className="truncate font-semibold">{viewerLabel}</span>
                  <EllipsisVertical className="ml-auto size-4" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>

              <DropdownMenuContent
                align="end"
                className="min-w-56"
                side="right"
                sideOffset={8}
              >
                <div className="flex items-center gap-2 rounded-md px-1 py-1.5">
                  <UserAvatar
                    email={viewer.email}
                    name={viewer.name}
                    picture={viewer.picture}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm leading-none font-semibold">
                      {viewerLabel}
                    </p>
                    <p className="truncate font-mono text-xs text-muted-foreground">
                      {viewer.email}
                    </p>
                  </div>
                </div>

                <DropdownMenuSeparator />

                <DropdownMenuItem>
                  <Users />
                  People
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <LineChart />
                  Usage
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <CreditCard />
                  Access & Billing
                </DropdownMenuItem>

                <DropdownMenuSeparator />

                <DropdownMenuItem onSelect={() => auth.logout()}>
                  <LogOut />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
