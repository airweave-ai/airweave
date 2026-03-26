import type { ReactNode } from 'react';

import type { LucideIcon } from 'lucide-react';
import {
  BarChart3,
  ChevronDown,
  EllipsisVertical,
  Folder,
  Home,
  KeyRound,
  LayoutDashboard,
  Plug,
  Plus,
  Settings,
  ShieldCheck,
  Webhook,
} from 'lucide-react';

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
} from './ui/sidebar';
import { Link, useMatchRoute } from '@tanstack/react-router';

type NavigationItem = {
  label: string;
  icon: LucideIcon;
  to: string;
  fuzzy?: boolean;
};

const navigationItems: NavigationItem[] = [
  { label: 'Home', icon: Home, to: '/' },
  { label: 'Overview', icon: LayoutDashboard, to: '/overview' },
  { label: 'Collections', icon: Folder, to: '/collections', fuzzy: true },
  { label: 'API Keys', icon: KeyRound, to: '/api-keys' },
  { label: 'Webhooks', icon: Webhook, to: '/webhooks' },
  { label: 'Auth Providers', icon: ShieldCheck, to: '/auth-providers' },
  { label: 'Airweave Connect', icon: Plug, to: '/connect' },
  { label: 'Usage', icon: BarChart3, to: '/usage' },
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
  return (
    <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-linear-to-br from-stone-200 via-stone-400 to-stone-700 text-[11px] font-semibold text-white">
      MJ
    </span>
  );
}

export function AppSidebar() {
  const matchRoute = useMatchRoute();
  return (
    <Sidebar>
      <SidebarHeader>
        <div className="flex items-center justify-between gap-2">
          <SidebarMenuButton
            className="w-auto flex-none gap-2 px-1.5 font-semibold"
            type="button"
          >
            <LogoMark />
            <span>Tonik Org</span>
            <ChevronDown className="size-4 text-sidebar-foreground/50" />
          </SidebarMenuButton>

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

        <SidebarMenuButton
          className="justify-center bg-sidebar-accent font-medium text-sidebar-accent-foreground hover:bg-sidebar-accent/80"
          type="button"
        >
          <Plus className="size-4" />
          <span>Create Collection</span>
        </SidebarMenuButton>
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
                          <Icon className="size-3.5" />
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
              <span className="truncate font-semibold">Admin User</span>
              <EllipsisVertical className="ml-auto size-4 text-sidebar-foreground/70" />
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
