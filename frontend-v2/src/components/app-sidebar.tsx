import { Link, useLocation, useParams } from "@tanstack/react-router";
import { Layers, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
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
  SidebarRail,
} from "@/components/ui/sidebar";
import { UserAccountDropdown } from "@/components/user-account-dropdown";
import { navItems } from "@/config/navigation";

export function AppSidebar() {
  const location = useLocation();
  const params = useParams({ strict: false }) as { orgSlug?: string };
  const orgSlug = params.orgSlug;

  // Don't show sidebar when no organization context
  if (!orgSlug) {
    return null;
  }

  // Check if a nav item is active - must consider org prefix
  const isActive = (to: string) => {
    // Replace $orgSlug placeholder with actual slug
    const fullPath = to.replace("$orgSlug", orgSlug);
    if (to === "/$orgSlug") {
      // Dashboard - exact match
      return (
        location.pathname === `/${orgSlug}` ||
        location.pathname === `/${orgSlug}/`
      );
    }
    return location.pathname.startsWith(fullPath);
  };

  return (
    <Sidebar collapsible="icon" side="left" className="py-2">
      <SidebarHeader>
        {/* Logo */}
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to="/$orgSlug" params={{ orgSlug }}>
                <div className="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                  <Layers className="size-4" />
                </div>
                <div className="flex flex-col gap-0.5 leading-none">
                  <span className="font-semibold">Airweave</span>
                  <span className="text-muted-foreground text-xs">v2.0</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>

        {/* Search Button */}
        <SidebarMenu>
          <SidebarMenuItem>
            <Button
              className="w-full justify-start gap-2 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
              size="sm"
            >
              <Plus className="size-4" />
              <span className="group-data-[collapsible=icon]:hidden">
                New collection
              </span>
            </Button>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    asChild
                    isActive={isActive(item.to)}
                    tooltip={item.title}
                  >
                    <Link to={item.to} params={{ orgSlug }}>
                      <item.icon />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <UserAccountDropdown variant="sidebar" />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
