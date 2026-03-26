import { useMemo } from 'react';
import {
  ChevronDown,
  EllipsisVertical,
  Home,
  Plus,
  Settings,
} from 'lucide-react';
import { Link, useMatchRoute } from '@tanstack/react-router';
import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { useAppSession } from '@/features/app-session';
import { Button } from '@/shared/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';
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
];

function LogoMark() {
  return (
    <span className="relative flex size-5 shrink-0 items-center justify-center overflow-hidden rounded-[0.35rem] bg-linear-to-br from-white to-zinc-300">
      <span className="grid grid-cols-2 gap-px">
        <span className="size-1 rounded-[1px] bg-black/80" />
        <span className="size-1 rounded-[1px] bg-black/80" />
        <span className="size-1 rounded-[1px] bg-black/80" />
        <span className="size-1 rounded-[1px] bg-black/40" />
      </span>
    </span>
  );
}

function SidebarIconFrame({ children }: { children: ReactNode }) {
  return (
    <span className="flex size-5 shrink-0 items-center justify-center rounded-[0.35rem] border border-sidebar-border">
      {children}
    </span>
  );
}

function UserAvatar() {
  const { viewer } = useAppSession();
  const initials = useMemo(() => {
    const label = viewer.name ?? viewer.email;

    return label
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join('');
  }, [viewer.email, viewer.name]);

  return (
    <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-linear-to-br from-stone-200 via-stone-400 to-stone-700 text-[11px] font-semibold text-white">
      {initials || 'AU'}
    </span>
  );
}

export function AppSidebar() {
  const matchRoute = useMatchRoute();
  const {
    currentOrganization,
    currentOrganizationId,
    organizations,
    setCurrentOrganizationId,
    viewer,
  } = useAppSession();

  return (
    <Sidebar variant="inset">
      <SidebarHeader>
        <div className="flex items-center justify-between gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <SidebarMenuButton
                className="w-auto flex-none gap-2 font-semibold data-open:[&_svg]:rotate-180"
                type="button"
              >
                <LogoMark />
                <span>{currentOrganization.name}</span>
                <ChevronDown className="size-4 text-sidebar-foreground/50 transition-[rotate]" />
              </SidebarMenuButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="min-w-79 rounded-sm">
              <DropdownMenuLabel className="px-2 py-1.5 font-mono uppercase">
                Organizations
              </DropdownMenuLabel>
              {organizations.length > 0 ? (
                <DropdownMenuRadioGroup
                  onValueChange={setCurrentOrganizationId}
                  value={currentOrganizationId}
                >
                  {organizations.map((organization) => (
                    <DropdownMenuRadioItem
                      key={organization.id}
                      className="rounded-xs p-2"
                      value={organization.id}
                    >
                      {organization.name}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              ) : (
                <DropdownMenuItem
                  className="rounded-xs p-2 text-muted-foreground"
                  disabled
                >
                  No organizations yet
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>

          <div className="flex items-center gap-1">
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

        <Button variant="secondary" data-icon="inline-start">
          <Plus />
          Create Collection
        </Button>
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
            <SidebarMenuButton className="gap-3" size="lg" type="button">
              <UserAvatar />
              <span className="truncate font-semibold">
                {viewer.name ?? viewer.email}
              </span>
              <EllipsisVertical className="ml-auto size-4 text-sidebar-foreground/70" />
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
