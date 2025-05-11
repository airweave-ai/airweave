import { Link, useLocation, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  RefreshCw,
  Settings,
  Database,
  User,
  RefreshCcw,
  Tag,
  Menu,
  MessageSquare,
  Bot,
  BookOpen,
  ExternalLink,
  Sun,
  Moon,
  Monitor,
  Check,
  Box
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useTheme } from "@/lib/theme-provider";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { GradientBackground, GradientCard } from "@/components/ui/gradient-background";
import { DiscordIcon } from "@/components/ui/discord-icon";
import { cn } from "@/lib/utils";
import { LogoutButton } from "@/components/LogoutButton";
import { UserProfileDropdown } from "@/components/UserProfileDropdown";

const DashboardLayout = () => {
  const location = useLocation();
  const { resolvedTheme, setTheme } = useTheme();

  // Determine which logo to use based on theme
  const logoSrc = resolvedTheme === "dark" ? "/logo-and-lettermark-light.svg" : "/logo-and-lettermark.svg";

  // Add array of routes that should be non-scrollable
  const nonScrollableRoutes = ['/chat', '/chat/'];

  // Check if current route should be non-scrollable
  const isNonScrollable = nonScrollableRoutes.some(route =>
    location.pathname === route || location.pathname.startsWith('/chat/'));

  const isRouteActive = (path: string) => {
    if (path === "/white-label") {
      return location.pathname.startsWith("/white-label");
    }
    if (path === "/sync") {
      if (location.pathname === "/sync/create") {
        return false;
      }
      return location.pathname.startsWith("/sync");
    }
    if (path === "/chat") {
      return location.pathname.startsWith("/chat");
    }
    return location.pathname === path;
  };

  const navigation = [
    {
      name: "Set up sync",
      href: "/sync/create",
      icon: RefreshCcw,
      isSpecial: true,
    },
    {
      name: "Dashboard",
      href: "/dashboard",
      icon: LayoutDashboard,
    },
    {
      name: "Chat Playground",
      href: "/chat",
      icon: Bot,
    },
  ];

  const configureNavigation = [
    {
      name: "Synchronizations",
      href: "/sync",
      icon: RefreshCw,
    },
    {
      name: "Sources",
      href: "/sources",
      icon: Box,
    },
    {
      name: "Destinations",
      href: "/destinations",
      icon: Database,
    },
    {
      name: "White Label",
      href: "/white-label",
      icon: Tag,
    },
    {
      name: "Settings",
      href: "/settings",
      icon: Settings,
    }
  ];

  const bottomNavigation = [];

  const NavLink = ({ item, isActive }: { item: typeof navigation[0], isActive: boolean }) => (
    <Link
      to={item.href}
      className={`flex items-center px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 ease-in-out ${
        isActive
          ? item.isSpecial
            ? "bg-gradient-to-r from-primary-300/90 to-secondary-300/90 dark:from-primary-700/70 dark:to-secondary-700/70 text-primary-900 dark:text-primary-100 shadow-sm"
            : "bg-primary/10 text-primary"
          : item.isSpecial
          ? "bg-gradient-to-r from-primary-300/70 to-secondary-300/70 dark:from-primary-500/50 dark:to-secondary-400/50 text-primary-800 dark:text-primary-100 shadow-sm hover:from-primary-400/80 hover:to-secondary-400/80 dark:hover:from-primary-400/60 dark:hover:to-secondary-300/60 hover:shadow transition-all duration-200 ease-in-out"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      }`}
    >
      <item.icon className="mr-3 h-5 w-5" />
      {item.name}
    </Link>
  );

  return (
    <GradientBackground className="min-h-screen">
      <GradientCard className="h-full">
        <div className="flex h-screen overflow-hidden">
          {/* Mobile Menu Button */}
          <div className="lg:hidden fixed top-4 left-4 z-[30]">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" className="bg-background-alpha-90">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0 bg-background-alpha-90 backdrop-blur-md">
                <div className="flex h-16 items-center px-6">
                  <Link to="/" className="flex items-center">
                    <img
                      src={logoSrc}
                      alt="Airweave"
                      className="h-6 pr-4"
                    />
                  </Link>
                </div>
                <nav className="flex flex-col justify-between h-[calc(100%-4rem)]">
                  <div className="space-y-1 px-3">
                    {navigation.map((item) => (
                      <NavLink
                        key={item.name}
                        item={item}
                        isActive={isRouteActive(item.href)}
                      />
                    ))}
                    <div className="mt-8">
                      <span className="px-3 text-xs font-semibold text-muted-foreground/70 tracking-wider">
                        CONFIGURE
                      </span>
                      <div className="mt-2">
                        {configureNavigation.map((item) => (
                          <NavLink
                            key={item.name}
                            item={item}
                            isActive={isRouteActive(item.href)}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="space-y-1 px-3 mb-6">
                    {bottomNavigation.map((item) => (
                      <NavLink
                        key={item.name}
                        item={item}
                        isActive={isRouteActive(item.href)}
                      />
                    ))}
                    <UserProfileDropdown />
                  </div>
                </nav>
              </SheetContent>
            </Sheet>
          </div>

          {/* Desktop Sidebar */}
          <div className="hidden w-64 lg:block fixed h-screen pl-2 pt-1 transition-all duration-300 ease-in-out z-20 shadow-sm border-r ">
            <div className="flex h-14 items-center px-4">
              <Link
                to="/"
                className="flex items-center transition-transform duration-200"
              >
                <img
                  src={logoSrc}
                  alt="Airweave"
                  className="h-8 pr-4"
                />
              </Link>
            </div>
            <nav className="flex flex-col justify-between h-[calc(100%-3.5rem)]">
              <div className="space-y-1 px-3 pt-3">
                {navigation.map((item) => (
                  <NavLink
                    key={item.name}
                    item={item}
                    isActive={isRouteActive(item.href)}
                  />
                ))}
                <div className="mt-8">
                  <span className="px-3 text-xs font-semibold text-muted-foreground/70 tracking-wider">
                    CONFIGURE
                  </span>
                  <div className="mt-2">
                    {configureNavigation.map((item) => (
                      <NavLink
                        key={item.name}
                        item={item}
                        isActive={isRouteActive(item.href)}
                      />
                    ))}
                  </div>
                </div>
              </div>
              <div className="space-y-1 px-3 mb-6">
                {bottomNavigation.map((item) => (
                  <NavLink
                    key={item.name}
                    item={item}
                    isActive={isRouteActive(item.href)}
                  />
                ))}
                <UserProfileDropdown />
              </div>
            </nav>
          </div>

          {/* Main content with conditionally scrollable area */}
          <div className="w-full lg:pl-64 flex flex-col h-screen">
            <div className={cn(
              "flex-1",
              isNonScrollable ? "overflow-hidden" : "overflow-auto"
            )}>
              {/* Top Navigation Bar - Now inside the scrollable area */}
                <header className={`h-16 sticky top-0 pr-2 backdrop-blur-sm z-10 ${resolvedTheme === 'dark' ? 'bg-black/20' : 'bg-background-alpha-10'}`}>

                <div className="flex justify-end items-center h-full px-6">
                  <nav className="flex items-center space-x-4">
                    {/* Discord icon */}
                    <a
                      href="https://discord.com/invite/484HY9Ehxt"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center hover:bg-background-alpha-40 h-8 w-8 rounded-md"
                    >
                    <DiscordIcon size={22}/>
                    </a>

                    {/* Get a demo button */}
                    <a
                      href="https://cal.com/lennert-airweave/airweave-q-a-demo"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button
                        variant="outline"
                        className="hidden md:flex border-primary/60 border-[1px] text-primary/90 hover:bg-primary/20 hover:text-foreground/65 h-8 px-3 text-sm"
                      >
                        Get a demo
                      </Button>
                    </a>

                    {/* Theme Switcher */}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="rounded-md h-8 w-8 hover:bg-background-alpha-40 text-muted-foreground">
                          {resolvedTheme === 'dark' ? (
                            <Moon className="h-6 w-6" />
                          ) : (
                            <Sun className="h-6 w-6" />
                          )}
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-32">
                        <DropdownMenuItem
                          onClick={() => setTheme('light')}
                          className="flex items-center justify-between cursor-pointer"
                        >
                          <div className="flex items-center">
                            <Sun className="mr-2 h-4 w-4" />
                            Light
                          </div>
                          {resolvedTheme === 'light' && <Check className="h-4 w-4" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setTheme('dark')}
                          className="flex items-center justify-between cursor-pointer"
                        >
                          <div className="flex items-center">
                            <Moon className="mr-2 h-4 w-4" />
                            Dark
                          </div>
                          {resolvedTheme === 'dark' && <Check className="h-4 w-4" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setTheme('system')}
                          className="flex items-center justify-between cursor-pointer"
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

              <div className={cn(
                "h-[calc(100%-4rem)]",
                isNonScrollable ? "overflow-hidden" : "pb-8"
              )}>
                  <Outlet />
              </div>
            </div>
          </div>
        </div>
      </GradientCard>
    </GradientBackground>
  );
};

export default DashboardLayout;
