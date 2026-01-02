import { useQuery } from "@tanstack/react-query";
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import {
  Building2,
  Check,
  ChevronDown,
  Layers,
  LogOut,
  Palette,
  Search,
  Settings,
} from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { navItems } from "@/config/navigation";
import { themeOptions } from "@/config/theme";
import { fetchOrganizations, type Organization } from "@/lib/api/organizations";
import { getRedirectUrl, useAuth0 } from "@/lib/auth-provider";
import { findOrgBySlug, generateOrgSlug } from "@/lib/org-utils";
import { useUISettings } from "@/stores/ui-settings";

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export function AppSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams({ strict: false }) as { orgSlug?: string };
  const theme = useUISettings((state) => state.theme);
  const setTheme = useUISettings((state) => state.setTheme);
  const { user, logout, getAccessTokenSilently } = useAuth0();
  const orgSlug = params.orgSlug;

  // Fetch organizations directly for the sidebar
  const { data: organizations = [] } = useQuery({
    queryKey: ["organizations"],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizations(token);
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // Find current org from URL slug
  const currentOrg = orgSlug ? findOrgBySlug(organizations, orgSlug) : null;

  // Check if a nav item is active - must consider org prefix
  const isActive = (to: string) => {
    if (!orgSlug) return false;
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

  const handleLogout = () => {
    logout({
      logoutParams: {
        returnTo: getRedirectUrl(),
      },
    });
  };

  const handleSwitchOrg = (org: Organization) => {
    const newOrgSlug = generateOrgSlug(org);
    // Navigate to the same page but in the new org context
    // Extract the current page path after the org slug
    const currentPath = location.pathname;
    const pathAfterOrg = orgSlug ? currentPath.replace(`/${orgSlug}`, "") : "";
    navigate({
      to: `/$orgSlug${pathAfterOrg || "/"}` as "/$orgSlug",
      params: { orgSlug: newOrgSlug },
    });
  };

  const userName = user?.name || user?.email || "User";
  const userAvatar = user?.picture || "";

  return (
    <Sidebar collapsible="icon" side="left" className="py-2">
      <SidebarHeader>
        {/* Logo */}
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link
                to={orgSlug ? "/$orgSlug" : "/"}
                params={orgSlug ? { orgSlug } : undefined}
              >
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

        {/* Organization Switcher */}
        {currentOrg && organizations.length > 0 && (
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton
                    className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                    tooltip={currentOrg.name}
                  >
                    <div className="bg-primary/10 flex size-5 items-center justify-center rounded">
                      <Building2 className="text-primary size-3" />
                    </div>
                    <span className="truncate font-medium group-data-[collapsible=icon]:hidden">
                      {currentOrg.name}
                    </span>
                    <ChevronDown className="text-muted-foreground ml-auto size-4 group-data-[collapsible=icon]:hidden" />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  side="bottom"
                  align="start"
                  className="w-[--radix-dropdown-menu-trigger-width] min-w-56"
                >
                  <DropdownMenuLabel className="text-muted-foreground text-xs font-normal">
                    Organizations
                  </DropdownMenuLabel>
                  {organizations.map((org) => (
                    <DropdownMenuItem
                      key={org.id}
                      onClick={() => handleSwitchOrg(org)}
                      className="gap-2"
                    >
                      <div className="bg-primary/10 flex size-5 items-center justify-center rounded">
                        <Building2 className="text-primary size-3" />
                      </div>
                      <span className="flex-1 truncate">{org.name}</span>
                      {org.id === currentOrg.id && (
                        <Check className="text-primary size-4" />
                      )}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        )}

        {/* Search Button */}
        <SidebarMenu>
          <SidebarMenuItem>
            <Button
              className="w-full justify-start gap-2 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
              size="sm"
            >
              <Search className="size-4" />
              <span className="group-data-[collapsible=icon]:hidden">
                Search your data
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
                    {orgSlug ? (
                      <Link to={item.to} params={{ orgSlug }}>
                        <item.icon />
                        <span>{item.title}</span>
                      </Link>
                    ) : (
                      <span className="cursor-not-allowed opacity-50">
                        <item.icon />
                        <span>{item.title}</span>
                      </span>
                    )}
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
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                  tooltip={userName}
                >
                  <Avatar className="size-5 rounded-lg">
                    <AvatarImage src={userAvatar} alt={userName} />
                    <AvatarFallback className="rounded-lg bg-slate-300 text-[60%] font-medium dark:bg-slate-700">
                      {getInitials(userName)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium">{userName}</span>
                  </div>
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                side="top"
                align="start"
                className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
              >
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    <Palette />
                    <span>Theme</span>
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent>
                    {themeOptions.map((option) => (
                      <DropdownMenuItem
                        key={option.value}
                        onClick={() => setTheme(option.value)}
                      >
                        <option.icon />
                        <span>{option.label}</span>
                        {theme === option.value && (
                          <Check className="ml-auto size-4" />
                        )}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
                <DropdownMenuSeparator />
                <DropdownMenuItem>
                  <Settings />
                  <span>Settings</span>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout}>
                  <LogOut />
                  <span>Log out</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
