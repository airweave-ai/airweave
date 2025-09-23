import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { Link, useNavigate } from 'react-router-dom';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger, DropdownMenuSub,
  DropdownMenuSubContent, DropdownMenuSubTrigger
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ExternalLink, MoreVertical, Building2, Settings,
  UserPlus, Crown, Shield, Users, Plus, LogOut, Check,
  CreditCard, Clock
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { BillingInfo } from '@/types';

// Consistent styling for all menu items
const menuItemClass = "flex items-center gap-2 px-2 py-1.5 text-sm cursor-pointer";
const subMenuItemClass = "flex items-center gap-2 px-2 py-1.5 text-sm cursor-pointer";
const externalLinkClass = "flex items-center justify-between px-2 py-1.5 text-sm";

interface MenuItemWithIconProps {
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
}

const MenuItemWithIcon = ({ icon, children, className, onClick, disabled }: MenuItemWithIconProps) => (
  <DropdownMenuItem
    onSelect={onClick}
    disabled={disabled}
    className={cn(menuItemClass, className)}
  >
    <span className="w-4 h-4 flex items-center justify-center text-muted-foreground">
      {icon}
    </span>
    <span className="flex-1">{children}</span>
  </DropdownMenuItem>
);

const ExternalMenuLink = ({ href, children }: { href: string; children: React.ReactNode }) => (
  <DropdownMenuItem asChild>
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={externalLinkClass}
    >
      <span className="flex items-center gap-2">{children}</span>
      <ExternalLink className="h-3 w-3 opacity-40" />
    </a>
  </DropdownMenuItem>
);

const InternalMenuLink = ({ to, icon, children }: { to: string; icon: React.ReactNode; children: React.ReactNode }) => (
  <DropdownMenuItem asChild>
    <Link to={to} className={menuItemClass}>
      <span className="w-4 h-4 flex items-center justify-center text-muted-foreground">
        {icon}
      </span>
      <span className="flex-1">{children}</span>
    </Link>
  </DropdownMenuItem>
);

// Consistent separator component
const MenuSeparator = () => <div className="h-px bg-border/10 my-1" />;

export function UserProfileDropdown() {
  const { user, logout } = useAuth();
  const { resolvedTheme } = useTheme();
  const navigate = useNavigate();
  const isDark = resolvedTheme === 'dark';

  const {
    organizations,
    currentOrganization,
    fetchUserOrganizations,
    switchOrganization
  } = useOrganizationStore();

  const [firstName, setFirstName] = useState<string>('');
  const [isLoadingOrgs, setIsLoadingOrgs] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [billingInfo, setBillingInfo] = useState<BillingInfo | null>(null);
  const [isLoadingBilling, setIsLoadingBilling] = useState(false);

  useEffect(() => {
    if (user?.name) {
      const nameParts = user.name.split(' ');
      setFirstName(nameParts[0] || '');
    }
  }, [user]);

  // Fetch user organizations when component mounts or user changes
  useEffect(() => {
    const loadOrganizations = async () => {
      if (user) {
        try {
          setIsLoadingOrgs(true);
          await fetchUserOrganizations();
        } catch (error) {
          console.error('Failed to load organizations:', error);
        } finally {
          setIsLoadingOrgs(false);
        }
      }
    };

    loadOrganizations();
  }, [user, fetchUserOrganizations]);

  // Fetch billing info when organization changes
  useEffect(() => {
    const fetchBillingInfo = async () => {
      if (currentOrganization) {
        try {
          setIsLoadingBilling(true);
          const response = await apiClient.get('/billing/subscription');
          if (response.ok) {
            const data = await response.json();
            setBillingInfo(data);
          }
        } catch (error) {
          console.error('Failed to fetch billing info:', error);
          setBillingInfo(null);
        } finally {
          setIsLoadingBilling(false);
        }
      }
    };

    fetchBillingInfo();
  }, [currentOrganization]);

  // Refetch organizations when dropdown opens to ensure fresh data
  useEffect(() => {
    const refreshOrganizations = async () => {
      if (dropdownOpen && user) {
        try {
          setIsLoadingOrgs(true);
          // Always fetch fresh data when dropdown opens
          await fetchUserOrganizations();
        } catch (error) {
          console.error('Failed to refresh organizations:', error);
        } finally {
          setIsLoadingOrgs(false);
        }
      }
    };

    // Only refresh when dropdown opens (becomes true)
    if (dropdownOpen) {
      refreshOrganizations();
    }
  }, [dropdownOpen, user, fetchUserOrganizations]);

  const handleLogout = () => {
    setDropdownOpen(false);
    apiClient.clearToken();
    logout();
  };

  const handleSwitchOrganization = (orgId: string) => {
    // If clicking on the already selected organization, just close the dropdown
    if (orgId === currentOrganization?.id) {
      setDropdownOpen(false);
      return;
    }

    // Update the organization in the store first
    switchOrganization(orgId);
    setDropdownOpen(false);

    // Do a full page reload to ensure clean state
    window.location.href = '/';
  };

  const handleCreateOrganization = () => {
    setDropdownOpen(false);
    navigate('/onboarding');
  };

  const getRoleIcon = (role: string) => {
    switch (role) {
      case 'owner': return <Crown className="h-3 w-3 text-brand-lime/90" />;
      case 'admin': return <Shield className="h-3 w-3 text-brand-lime/90" />;
      default: return <Users className="h-3 w-3 text-brand-lime/90" />;
    }
  };

  const getPlanBadge = () => {
    if (!billingInfo || isLoadingBilling) return null;

    const planDisplayName = {
      developer: 'Developer',
      pro: 'Pro',
      team: 'Team',
      enterprise: 'Enterprise'
    }[billingInfo.plan] || billingInfo.plan;

    return (
      <Badge variant="secondary" className="text-xs px-1.5 py-0 h-5">
        {planDisplayName}
      </Badge>
    );
  };

  const closeDropdown = () => setDropdownOpen(false);

  return (
    <>
      <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
        <DropdownMenuTrigger asChild>
          <button className="flex items-center justify-between py-2 text-sm rounded-lg w-full hover:bg-muted transition-all duration-200 outline-none focus:outline-none focus:ring-0">
            <div className="flex items-center gap-3">
              <Avatar className="h-8 w-8">
                <AvatarImage src={user?.picture} alt={user?.name || "User"} />
                <AvatarFallback className="bg-primary/10 text-primary text-bold text-xs">
                  {firstName
                    ? firstName[0]
                    : user?.email?.substring(0, 1).toUpperCase() || 'U'}
                </AvatarFallback>
              </Avatar>
              <div className="flex flex-col items-start min-w-0">
                <span className="text-foreground truncate max-w-32">
                  {user?.name || "User"}
                </span>
                {currentOrganization && (
                  <span className="text-xs text-muted-foreground/70 truncate max-w-32">
                    {currentOrganization.name}
                  </span>
                )}
              </div>
            </div>
            <MoreVertical className="h-4 w-4 text-muted-foreground/60" />
          </button>
        </DropdownMenuTrigger>

        <DropdownMenuContent
          className="w-[300px] p-1 ml-1 shadow-xs"
          align="end"
          side="top"
          sideOffset={8}
          onEscapeKeyDown={closeDropdown}
          onInteractOutside={closeDropdown}
        >
          {/* User Info Section */}
          <div className="px-2 py-1.5 border-b border-border/10 bg-muted/20">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground font-medium truncate">
                {user?.email}
              </p>
              {getPlanBadge()}
            </div>
          </div>

          {/* Organization Switcher */}
          <DropdownMenuSub>
            <DropdownMenuSubTrigger className={cn(subMenuItemClass, "px-2 py-1.5 cursor-pointer")}>
              <span className="flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                {currentOrganization?.name || 'Select Organization'}
              </span>
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-72 p-1 shadow-xs animate-none max-h-96 overflow-y-auto" alignOffset={-120}>
              {isLoadingOrgs ? (
                <DropdownMenuItem disabled className="px-2 py-1.5 text-sm text-muted-foreground">
                  Loading organizations...
                </DropdownMenuItem>
              ) : organizations.length > 0 ? (
                <>
                  {organizations.map((org) => {
                    const isSelected = org.id === currentOrganization?.id;

                    return (
                      <DropdownMenuItem
                        key={org.id}
                        onSelect={() => handleSwitchOrganization(org.id)}
                        className={cn(
                          "flex items-center justify-between px-2 py-2.5 rounded-md transition-colors cursor-pointer",
                          isSelected
                            ? "bg-muted/50 text-foreground cursor-default"
                            : "hover:bg-muted/30"
                        )}
                      >
                        <div className="flex items-center gap-2.5 min-w-0 flex-1">
                          <span className="w-4 h-4 flex items-center justify-center">
                            <Building2 className="h-4 w-4 text-muted-foreground/60" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm truncate font-medium">{org.name}</span>
                              {getRoleIcon(org.role)}
                            </div>
                            {org.is_primary && (
                              <div className="text-xs mt-0.5 text-brand-yellow">Primary organization</div>
                            )}
                          </div>
                        </div>
                        <div className="shrink-0 ml-2">
                          {isSelected && (
                            <Check className="h-4 w-4 text-muted-foreground/60" />
                          )}
                        </div>
                      </DropdownMenuItem>
                    );
                  })}

                  <MenuSeparator />

                  <MenuItemWithIcon
                    icon={<Plus className="h-4 w-4" />}
                    onClick={handleCreateOrganization}
                    className="text-primary data-[highlighted]:bg-transparent"
                  >
                    Create Organization
                  </MenuItemWithIcon>
                </>
              ) : (
                <>
                  <DropdownMenuItem disabled className="px-2 py-1.5 text-sm text-muted-foreground">
                    No organizations found
                  </DropdownMenuItem>

                  <MenuSeparator />

                  <MenuItemWithIcon
                    icon={<Plus className="h-4 w-4" />}
                    onClick={handleCreateOrganization}
                    className="text-primary data-[highlighted]:bg-transparent"
                  >
                    Create Organization
                  </MenuItemWithIcon>
                </>
              )}
            </DropdownMenuSubContent>
          </DropdownMenuSub>

          {/* Organization Management */}
          {currentOrganization && ['owner', 'admin'].includes(currentOrganization.role) && (
            <>
              <MenuSeparator />

              <InternalMenuLink
                to="/organization/settings?tab=members"
                icon={<UserPlus className="h-4 w-4" />}
              >
                Invite Members
              </InternalMenuLink>

              <InternalMenuLink
                to="/organization/settings"
                icon={<Settings className="h-4 w-4" />}
              >
                Organization Settings
              </InternalMenuLink>

              {/* Billing Link */}
              {billingInfo && !billingInfo.has_active_subscription && (
                <InternalMenuLink
                  to="/organization/settings?tab=billing"
                  icon={<CreditCard className="h-4 w-4" />}
                >
                  Complete Billing Setup
                </InternalMenuLink>
              )}
            </>
          )}

          <MenuSeparator />

          {/* External Links */}
          <ExternalMenuLink href="https://airweave.ai">
            Blog
          </ExternalMenuLink>

          <ExternalMenuLink href="https://docs.airweave.ai">
            Documentation
          </ExternalMenuLink>

          <ExternalMenuLink href="https://discord.gg/484HY9Ehxt">
            Join Discord
          </ExternalMenuLink>

          <MenuSeparator />

          {/* Logout */}
          <MenuItemWithIcon
            icon={<LogOut className="h-4 w-4" />}
            onClick={handleLogout}
            className="text-muted-foreground/80"
          >
            Sign out
          </MenuItemWithIcon>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
}
