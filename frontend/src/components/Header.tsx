import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger
} from "@/components/ui/sheet";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { useTheme } from "@/lib/theme-provider";

export const Header = () => {
  const [open, setOpen] = React.useState(false);
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();

  // Determine which logo to use based on theme
  const logoSrc = resolvedTheme === "dark" ? "/logo-and-lettermark-light.svg" : "/logo-and-lettermark.svg";

  const handleGetStarted = () => {
    navigate("/login");
  };

  return (
    <header className="w-full border-b">
      <div className="container flex h-16 items-center justify-between">
        {/* Logo */}
        <div className="flex items-center space-x-2">
          <Link to="/" className="flex items-center space-x-2">
            <img
              src={logoSrc}
              alt="Airweave"
              className="h-8"
            />
          </Link>
        </div>

        {/* Mobile Menu Trigger */}
        <div className="md:hidden">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon">
                <Menu className="h-6 w-6" />
                <span className="sr-only">Toggle Menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="right">
              <SheetHeader>
                <SheetTitle>Menu</SheetTitle>
              </SheetHeader>
              <div className="mt-4 flex flex-col space-y-4">
                <Link
                  to="/sources"
                  className="text-sm font-medium transition-colors hover:text-primary-400"
                  onClick={() => setOpen(false)}
                >
                  Integrations
                </Link>
                <Link
                  to="/sync"
                  className="text-sm font-medium transition-colors hover:text-primary-400"
                  onClick={() => setOpen(false)}
                >
                  Vector Sync
                </Link>
                <div className="pt-4">
                  <ThemeToggle />
                </div>
              </div>
            </SheetContent>
          </Sheet>
        </div>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center space-x-6">
          <Link
            to="/sources"
            className="text-sm font-medium hover:text-primary-400 transition-colors"
          >
            Integrations
          </Link>
          <Link
            to="/sync"
            className="text-sm font-medium hover:text-primary-400 transition-colors"
          >
            Vector Sync
          </Link>
          <ThemeToggle />
        </nav>

        {/* "Get Started" button remains visible on all screens */}
        <div className="ml-4">
          <Button onClick={handleGetStarted}>Get Started</Button>
        </div>
      </div>
    </header>
  );
};
