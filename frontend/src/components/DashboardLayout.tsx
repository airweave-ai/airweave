import { Link, useLocation, Outlet, useNavigate, useSearchParams } from "react-router-dom";
import {
  Settings,
  Menu,
  Sun,
  Moon,
  Monitor,
  Check,
  Plus,
  Key,
  Tag,
  ChevronDown,
  ChevronRight,
  Box,
  ExternalLink,
  LayoutGrid,
  Home,
  Shield,
  Github,  // Add Github icon
  FileText, // Change from Book to FileText
  Webhook,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useTheme } from "@/lib/theme-provider";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { GradientBackground, GradientCard } from "@/components/ui/gradient-background";
import { DiscordIcon } from "@/components/ui/discord-icon";
import { cn } from "@/lib/utils";
import { UserProfileDropdown } from "@/components/UserProfileDropdown";
import { useState, useEffect, useCallback, useRef, memo, useMemo } from "react";
import { apiClient } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { onCollectionEvent, COLLECTION_DELETED, COLLECTION_CREATED, COLLECTION_UPDATED } from "@/lib/events";
import { APIKeysSettings } from "@/components/settings/APIKeysSettings";
import { useCollectionsStore, useSourcesStore } from "@/lib/stores";
import { useOrganizationStore } from "@/lib/stores/organizations";
import { useUsageStore } from "@/lib/stores/usage";
import { getStoredErrorDetails, clearStoredErrorDetails } from "@/lib/error-utils";
import { BillingGuard } from "@/components/BillingGuard";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { SingleActionCheckResponse } from "@/types";
import { SidePanelFlow } from "@/components/shared/SidePanelFlow"; // Import the new SidePanel
import { useSidePanelStore } from "@/lib/stores/sidePanelStore"; // Import the new store
import { useCollectionCreationStore } from "@/stores/collectionCreationStore"; // Import collection creation store
import { CollectionCreationModal } from "@/components/CollectionCreationModal"; // Import the modal
import { UsageChecker } from "@/components/UsageChecker"; // App-level usage checker

// Memoized Collections Section to prevent re-renders of the entire sidebar
const CollectionsSection = memo(() => {
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(true);
  const { collections, totalCount, isLoading: isLoadingCollections, error: collectionError, fetchCollections, fetchCollectionsCount } = useCollectionsStore();
  const { currentOrganization } = useOrganizationStore();

  // Initialize collections and event listeners
  useEffect(() => {
    fetchCollections();
    fetchCollectionsCount();
    const unsubscribe = useCollectionsStore.getState().subscribeToEvents();
    return unsubscribe;
  }, [fetchCollections, fetchCollectionsCount]);

  // Active status for nav items
  const isActive = useCallback((path: string) => {
    return location.pathname === path;
  }, [location.pathname]);

  // Common navigation item styling
  const getNavItemStyles = useCallback((active: boolean) => cn(
    "flex items-center px-3 py-2 text-sm rounded-lg relative transition-all duration-200",
    "hover:bg-primary/10 group max-w-[214px]",
    active
      ? "text-primary font-medium bg-primary/10 shadow-sm"
      : "text-muted-foreground hover:text-foreground"
  ), []);

  // Toggle collections open/closed
  const toggleOpen = useCallback(() => {
    setIsOpen(prev => !prev);
  }, []);

  return (
    <div className="space-y-0.5 w-[214px]">
      {/* Collections Header - Consistent Width */}
      <button
        onClick={toggleOpen}
        className="flex items-center justify-between w-full px-3 py-2 text-sm rounded-lg text-muted-foreground hover:text-foreground hover:bg-primary/5 transition-all duration-200"
      >
        <span className="font-bold flex items-center">
          <LayoutGrid className="mr-2 h-4 w-4 opacity-70" />
          Collections
        </span>
        <div className="transition-transform duration-200" style={{ transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}>
          <ChevronDown className="h-4 w-4" />
        </div>
      </button>

      {/* Collections Content - Simple CSS Transition */}
      <div
        className={cn(
          "overflow-hidden ml-1 transition-all duration-200 ease-in-out",
          isOpen ? "max-h-[800px] opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <div className="pl-1 border-l border-border/30 space-y-0.5">
          {isLoadingCollections ? (
            <div className="px-2 py-1 text-xs text-muted-foreground">Loading...</div>
          ) : collectionError ? (
            <div className="px-2 py-1 text-xs text-destructive">{collectionError}</div>
          ) : collections.length === 0 ? (
            <div className="px-2 py-1 text-xs text-muted-foreground">No collections</div>
          ) : (
            <>
              {/* Display maximum 20 collections */}
              {collections.slice(0, 20).map((collection) => (
                <Link
                  key={collection.id}
                  to={`/collections/${collection.readable_id}`}
                  className={getNavItemStyles(isActive(`/collections/${collection.readable_id}`))}
                >
                  <LayoutGrid className="mr-2 h-3.5 w-3.5 opacity-70 group-hover:opacity-100 transition-opacity" />
                  <span className="truncate">{collection.name}</span>
                  {isActive(`/collections/${collection.readable_id}`) && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-primary rounded-full transform -translate-x-1.5" />
                  )}
                </Link>
              ))}

              {/* Always show "See all" link with more padding and margin for visibility */}
              <Link
                to="/collections"
                className="flex items-center px-3 py-2.5 text-sm rounded-lg text-primary hover:text-primary/80 hover:bg-primary/10 mt-3 mb-2 transition-all duration-200"
              >
                <ExternalLink className="mr-2 h-3.5 w-3.5 opacity-70" />
                <span>See all{totalCount !== null ? ` (${totalCount})` : collections.length > 0 ? ` (${collections.length})` : ''}</span>
              </Link>

            </>
          )}
        </div>
      </div>
    </div>
  );
});

CollectionsSection.displayName = 'CollectionsSection';

// Memoized Logo component
const Logo = memo(({ theme }: { theme: string }) => {
  const logoSrc = theme === "dark" ? "/logo-airweave-darkbg.svg" : "/logo-airweave-lightbg.svg";

  return (
    <Link to="/" className="flex items-center">
      <img src={logoSrc} alt="Airweave" className="h-8" />
    </Link>
  );
});

Logo.displayName = 'Logo';

// Memoized NavItem component
const NavItem = memo(({ to, isActive, icon, children }: {
  to: string;
  isActive: boolean;
  icon: React.ReactNode;
  children: React.ReactNode;
}) => {
  const navItemStyles = cn(
    "flex items-center px-3 py-2 text-sm rounded-lg relative transition-all duration-200",
    "hover:bg-primary/10 group max-w-[214px]",
    isActive
      ? "text-primary font-medium bg-primary/10 shadow-sm"
      : "text-muted-foreground hover:text-foreground"
  );

  return (
    <Link to={to} className={navItemStyles}>
      {icon}
      <span className="font-semibold">{children}</span>
    </Link>
  );
});

NavItem.displayName = 'NavItem';

// Main DashboardLayout component
const DashboardLayout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { resolvedTheme, setTheme } = useTheme();
  const { fetchSources } = useSourcesStore();
  const { currentOrganization } = useOrganizationStore();
  const { openPanel } = useSidePanelStore(); // Get the function to open the panel

  // Usage check from store
  const checkActions = useUsageStore(state => state.checkActions);
  const actionChecks = useUsageStore(state => state.actionChecks);
  const isCheckingUsage = useUsageStore(state => state.isLoading);

  // Derived states from usage store
  const sourceConnectionsAllowed = actionChecks.source_connections?.allowed ?? true;
  const entitiesAllowed = actionChecks.entities?.allowed ?? true;
  const usageCheckDetails = actionChecks;

  // Add array of routes that should be non-scrollable
  const nonScrollableRoutes = ['/chat', '/chat/'];

  // Check if current route should be non-scrollable
  const isNonScrollable = nonScrollableRoutes.some(route =>
    location.pathname === route || location.pathname.startsWith('/chat/'));

  // Usage checking is now handled by UsageChecker component at app level

  const handleCreateCollection = useCallback(() => {
    // Use the modal instead of side panel for collection creation
    const store = useCollectionCreationStore.getState();
    store.openForCreateCollection();
  }, []);

  // Usage limits are now checked by UsageChecker component

  // Memoize active status checks
  const isDashboardActive = useMemo(() =>
    location.pathname === "/",
    [location.pathname]);


  const isApiKeysActive = useMemo(() =>
    location.pathname === '/api-keys',
    [location.pathname]);

  const isAuthProvidersActive = useMemo(() =>
    location.pathname.startsWith('/auth-providers'),
    [location.pathname]);

  const isWebhooksActive = useMemo(() =>
    location.pathname === '/webhooks',
    [location.pathname]);

  // Fully memoized SidebarContent component
  const SidebarContent = useMemo(() => (
    <div className="flex flex-col h-full">
      <div className="flex h-14 items-center px-4 mb-2">
        <Logo theme={resolvedTheme} />
      </div>

      <ScrollArea className="flex-1 px-2 py-1 min-h-[300px]">
        <div className="space-y-0 pr-3 pb-4">
          {/* Create Collection Button */}
          <div className="pb-1 pt-1">
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0} className="w-full">
                    <Button
                      onClick={handleCreateCollection}
                      variant="outline"
                      size="sm"
                      disabled={!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage}
                      className={cn(
                        "flex items-center justify-center w-[214px] gap-1.5 text-sm bg-background border rounded-lg py-2 hover:shadow-sm",
                        (!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage)
                          ? "opacity-50 cursor-not-allowed text-muted-foreground border-border"
                          : "text-primary hover:bg-primary/15 border-primary/60 hover:text-primary font-medium transition-all duration-200"
                      )}
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Create collection
                    </Button>
                  </span>
                </TooltipTrigger>
                {(!sourceConnectionsAllowed || !entitiesAllowed) && (
                  <TooltipContent className="max-w-xs">
                    <p className="text-xs">
                      {!sourceConnectionsAllowed && usageCheckDetails.source_connections?.reason === 'usage_limit_exceeded' ? (
                        <>
                          Source connection limit reached.{' '}
                          <a
                            href="/organization/settings?tab=billing"
                            className="underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            Upgrade your plan
                          </a>
                          {' '}for more connections.
                        </>
                      ) : !entitiesAllowed && usageCheckDetails.entities?.reason === 'usage_limit_exceeded' ? (
                        <>
                          Entity processing limit reached.{' '}
                          <a
                            href="/organization/settings?tab=billing"
                            className="underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            Upgrade your plan
                          </a>
                          {' '}to process more data.
                        </>
                      ) : (
                        'Unable to create collection at this time.'
                      )}
                    </p>
                  </TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
          </div>

          {/* Home Button */}
          <div className="pb-1 pt-2">
            <NavItem
              to="/"
              isActive={isDashboardActive}
              icon={<Home className="mr-2 h-4 w-4 opacity-70 group-hover:opacity-100 transition-opacity" />}
            >
              Dashboard
            </NavItem>
          </div>

          {/* Collections Section - Isolated and Memoized */}
          <CollectionsSection />

          {/* API Keys Section */}
          <div>
            <NavItem
              to="/api-keys"
              isActive={isApiKeysActive}
              icon={<Key className="mr-2 h-4 w-4 opacity-70 group-hover:opacity-100 transition-opacity" />}
            >
              API keys
            </NavItem>
          </div>

          {/* Auth Providers Section */}
          <div>
            <NavItem
              to="/auth-providers"
              isActive={isAuthProvidersActive}
              icon={<Shield className="mr-2 h-4 w-4 opacity-70 group-hover:opacity-100 transition-opacity" />}
            >
              Auth Providers
            </NavItem>
          </div>

          {/* Webhooks Section */}
          <div>
            <NavItem
              to="/webhooks"
              isActive={isWebhooksActive}
              icon={<Webhook className="mr-2 h-4 w-4 opacity-70 group-hover:opacity-100 transition-opacity" />}
            >
              Webhooks
              <span className="ml-1.5 text-[9px] font-medium text-muted-foreground/60 uppercase tracking-wide">beta</span>
            </NavItem>
          </div>

        </div>
      </ScrollArea>

      {/* User Profile Section */}
      <div className="mt-auto pt-2 pb-3 px-3 border-t border-border/30">
        <UserProfileDropdown />
      </div>
    </div>
  ), [resolvedTheme, handleCreateCollection, isDashboardActive, isApiKeysActive, isAuthProvidersActive, isWebhooksActive, currentOrganization?.id, sourceConnectionsAllowed, entitiesAllowed, isCheckingUsage, usageCheckDetails]);

  // Main component render
  return (
    <GradientBackground className="min-h-screen">
      <GradientCard className="h-full">
        {/* Global usage checker - checks once at app level */}
        <UsageChecker />

        {/* Global modals and panels - available on all pages */}
        <CollectionCreationModal />
        <SidePanelFlow />

        <div className="flex h-screen overflow-hidden">
          {/* Mobile Menu Button */}
          <div className="lg:hidden fixed top-4 left-4 z-[30]">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" className="bg-background-alpha-90 rounded-lg shadow-sm hover:bg-background-alpha-100 transition-all duration-200">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0 bg-background-alpha-90 backdrop-blur-md">
                {SidebarContent}
              </SheetContent>
            </Sheet>
          </div>

          {/* Desktop Sidebar */}
          <div className="hidden w-[240px] lg:block fixed h-screen transition-all duration-300 ease-in-out z-20 border-r border-border/40 bg-background/95">
            {SidebarContent}
          </div>

          {/* Main content with conditionally scrollable area */}
          <div className="w-full lg:pl-[240px] flex flex-col h-screen">
            <div className={cn(
              "flex-1",
              isNonScrollable ? "overflow-hidden" : "overflow-auto"
            )}>
              {/* Top Navigation Bar - Now inside the scrollable area */}
              <header className={`h-16 sticky top-0 pr-2 backdrop-blur-sm z-10 ${resolvedTheme === 'dark' ? 'bg-background/80' : 'bg-background/95'} border-b border-border/30`}>
                <div className="flex justify-end items-center h-full px-6">
                  <nav className="flex items-center space-x-4">
                    {/* GitHub icon */}
                    <a
                      href="https://github.com/airweave-ai/airweave"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center hover:bg-black/[0.04] dark:hover:bg-white/[0.04] h-8 w-8 rounded-full transition-colors duration-150 ease-out"
                    >
                      <Github size={20} className="text-muted-foreground" />
                    </a>



                    {/* Discord icon */}
                    <a
                      href="https://discord.com/invite/484HY9Ehxt"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center hover:bg-black/[0.04] dark:hover:bg-white/[0.04] h-8 w-8 rounded-full transition-colors duration-150 ease-out"
                    >
                      <DiscordIcon size={20} />
                    </a>

                    {/* Docs icon */}
                    <a
                      href="https://docs.airweave.ai/welcome"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center hover:bg-black/[0.04] dark:hover:bg-white/[0.04] h-8 w-8 rounded-full transition-colors duration-150 ease-out"
                    >
                      <FileText size={20} className="text-muted-foreground" />
                    </a>

                    {/* Get a demo button */}
                    <a
                      href="https://cal.com/lennert-airweave/airweave-demo"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button
                        variant="outline"
                        className="hidden md:flex border-primary/60 border-[1px] text-primary/90 hover:bg-primary/10 hover:text-foreground/65 h-9 px-4 text-sm rounded-lg transition-all duration-200 hover:shadow-sm"
                      >
                        Get a Demo
                      </Button>
                    </a>

                    {/* Theme Switcher */}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="rounded-lg h-8 w-8 hover:bg-background-alpha-40 text-muted-foreground transition-all duration-200">
                          {resolvedTheme === 'dark' ? (
                            <Moon className="h-[18px] w-[18px]" />
                          ) : (
                            <Sun className="h-[18px] w-[18px]" />
                          )}
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-32 rounded-lg overflow-hidden">
                        <DropdownMenuItem
                          onClick={() => setTheme('light')}
                          className="flex items-center justify-between cursor-pointer transition-colors"
                        >
                          <div className="flex items-center">
                            <Sun className="mr-2 h-4 w-4" />
                            Light
                          </div>
                          {resolvedTheme === 'light' && <Check className="h-4 w-4" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setTheme('dark')}
                          className="flex items-center justify-between cursor-pointer transition-colors"
                        >
                          <div className="flex items-center">
                            <Moon className="mr-2 h-4 w-4" />
                            Dark
                          </div>
                          {resolvedTheme === 'dark' && <Check className="h-4 w-4" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setTheme('system')}
                          className="flex items-center justify-between cursor-pointer transition-colors"
                        >
                          <div className="flex items-center">
                            <Monitor className="mr-2 h-4 w-4" />
                            System
                          </div>
                          {(resolvedTheme !== 'dark' && resolvedTheme !== 'light') && <Check className="h-4 w-4" />}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </nav>
                </div>
              </header>

              {location.pathname.startsWith('/billing') ? (
                // Don't wrap billing pages with BillingGuard to avoid infinite loops
                <div className={cn(
                  "h-[calc(100%-4rem)]",
                  isNonScrollable ? "overflow-hidden" : "pb-8"
                )}>
                  {location.pathname === "/api-keys" ? (
                    <div className="container pb-8 pt-8">
                      <div className="flex items-center gap-2 mb-8">
                        <Key className="h-6 w-6" />
                        <h1 className="text-2xl font-semibold">API Keys</h1>
                      </div>
                      <div className="max-w-4xl">
                        <APIKeysSettings />
                      </div>
                    </div>
                  ) : (
                    <Outlet />
                  )}
                </div>
              ) : (
                <BillingGuard>
                  <div className={cn(
                    "h-[calc(100%-4rem)]",
                    isNonScrollable ? "overflow-hidden" : "pb-8"
                  )}>
                    {location.pathname === "/api-keys" ? (
                      <div className="container pb-8 pt-8">
                        <div className="flex items-center gap-2 mb-8">
                          <Key className="h-6 w-6" />
                          <h1 className="text-2xl font-semibold">API Keys</h1>
                        </div>
                        <div className="max-w-4xl">
                          <APIKeysSettings />
                        </div>
                      </div>
                    ) : (
                      <Outlet />
                    )}
                  </div>
                </BillingGuard>
              )}
            </div>
          </div>
        </div>
      </GradientCard>
    </GradientBackground>
  );
};

export default DashboardLayout;
