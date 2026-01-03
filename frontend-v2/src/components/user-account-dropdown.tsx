import { useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate, useParams } from "@tanstack/react-router";
import { Building2, Check, LogOut, Palette, Plus } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarMenuButton } from "@/components/ui/sidebar";
import { themeOptions } from "@/config/theme";
import { fetchOrganizations, type Organization } from "@/lib/api/organizations";
import { getRedirectUrl, useAuth0 } from "@/lib/auth-provider";
import { findOrgBySlug, generateOrgSlug } from "@/lib/org-utils";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { useUISettings } from "@/stores/ui-settings";

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

interface UserAccountDropdownProps {
  /** Style variant for the trigger button */
  variant?: "sidebar" | "standalone";
  /** Optional class name for the trigger */
  className?: string;
}

export function UserAccountDropdown({
  variant = "sidebar",
  className,
}: UserAccountDropdownProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams({ strict: false }) as { orgSlug?: string };
  const theme = useUISettings((state) => state.theme);
  const setTheme = useUISettings((state) => state.setTheme);
  const { user, logout, getAccessTokenSilently } = useAuth0();
  const orgSlug = params.orgSlug;

  // Fetch organizations
  const { data: organizations = [] } = useQuery({
    queryKey: queryKeys.organizations.all,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizations(token);
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // Find current org from URL slug
  const currentOrg = orgSlug ? findOrgBySlug(organizations, orgSlug) : null;

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

  const handleCreateOrganization = () => {
    navigate({ to: "/onboarding" });
  };

  const userName = user?.name || user?.email || "User";
  const userAvatar = user?.picture || "";

  const triggerContent = (
    <>
      <Avatar className="size-5 rounded-lg">
        <AvatarImage src={userAvatar} alt={userName} />
        <AvatarFallback className="rounded-lg bg-slate-700 text-[60%] font-medium">
          {getInitials(userName)}
        </AvatarFallback>
      </Avatar>
      <div className="grid flex-1 text-left text-sm leading-tight">
        <span className="truncate font-medium">{userName}</span>
      </div>
    </>
  );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        {variant === "sidebar" ? (
          <SidebarMenuButton
            className={cn(
              "data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground",
              className
            )}
            tooltip={userName}
          >
            {triggerContent}
          </SidebarMenuButton>
        ) : (
          <Button
            variant="ghost"
            className={cn("-ml-3 h-auto gap-2 px-3 py-2", className)}
          >
            {triggerContent}
          </Button>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side={variant === "sidebar" ? "top" : "bottom"}
        align="start"
        className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
      >
        {organizations.length > 0 && (
          <>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>
                <Building2 />
                <span>Switch organization</span>
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent>
                {organizations.map((org) => (
                  <DropdownMenuItem
                    key={org.id}
                    onClick={() => handleSwitchOrg(org)}
                  >
                    <Building2 />
                    <span>{org.name}</span>
                    {currentOrg && org.id === currentOrg.id && (
                      <Check className="ml-auto size-4" />
                    )}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleCreateOrganization}>
                  <Plus />
                  <span>Create organization</span>
                </DropdownMenuItem>
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          </>
        )}
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
                {theme === option.value && <Check className="ml-auto size-4" />}
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuItem variant="destructive" onClick={handleLogout}>
          <LogOut />
          <span>Log out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
