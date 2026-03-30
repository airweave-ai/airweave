import { IconBrandGithub } from '@tabler/icons-react';
import { Link } from '@tanstack/react-router';
import { ChevronsUpDown } from 'lucide-react';
import {
  OrganizationSwitcher,
  OrganizationSwitcherMenu,
  OrganizationSwitcherTrigger,
} from '@/features/organizations';
import { useAppSession } from '@/features/app-session';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbSeparator,
} from '@/shared/ui/breadcrumb';
import { AirweaveLogo } from '@/shared/ui/airweave-logo';
import { Button } from '@/shared/ui/button';
import { LogoMark } from '@/shared/ui/logo-mark';
import { SidebarTrigger } from '@/shared/ui/sidebar';

const resourceLinks = [
  {
    href: 'https://docs.airweave.ai/welcome',
    label: 'Docs',
  },
  {
    href: 'https://discord.gg/484HY9Ehxt',
    label: 'Support',
  },
] as const;

export function AppHeader() {
  const {
    currentOrganization,
    currentOrganizationId,
    organizations,
    setCurrentOrganizationId,
  } = useAppSession();

  return (
    <header className="border-b bg-background px-4 py-3 sm:px-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="md:hidden" />

          <Breadcrumb>
            <BreadcrumbList className="gap-1">
              <BreadcrumbItem className="shrink-0">
                <BreadcrumbLink asChild>
                  <Button variant="ghost" size="icon" asChild>
                    <Link to="/">
                      <AirweaveLogo className="size-4 text-foreground" />
                      <span className="sr-only">Dashboard</span>
                    </Link>
                  </Button>
                </BreadcrumbLink>
              </BreadcrumbItem>

              <BreadcrumbSeparator className="text-foreground/20">
                <span>/</span>
              </BreadcrumbSeparator>

              <BreadcrumbItem className="min-w-0">
                <OrganizationSwitcher>
                  <OrganizationSwitcherTrigger asChild>
                    <Button
                      className="gap-1 text-sm"
                      type="button"
                      variant="ghost"
                      size="sm"
                    >
                      <LogoMark className="size-3 rounded-xs" />
                      <span className="truncate text-foreground">
                        {currentOrganization.name}
                      </span>
                      <ChevronsUpDown
                        className="size-3.5 shrink-0 text-muted-foreground"
                        data-role="indicator"
                      />
                    </Button>
                  </OrganizationSwitcherTrigger>
                  <OrganizationSwitcherMenu
                    className="min-w-79"
                    currentOrganizationId={currentOrganizationId}
                    onCurrentOrganizationChange={setCurrentOrganizationId}
                    organizations={organizations}
                    sideOffset={10}
                  />
                </OrganizationSwitcher>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </div>

        <nav className="flex items-center justify-end gap-2">
          {resourceLinks.map((link) => (
            <Button
              key={link.label}
              asChild
              className="text-muted-foreground"
              variant="ghost"
            >
              <a href={link.href} rel="noreferrer" target="_blank">
                {link.label}
              </a>
            </Button>
          ))}

          <Button
            asChild
            className="text-muted-foreground"
            size="icon"
            variant="ghost"
          >
            <a
              aria-label="GitHub repository"
              href="https://github.com/airweave-ai/airweave"
              rel="noreferrer"
              target="_blank"
            >
              <IconBrandGithub className="size-4" />
            </a>
          </Button>
        </nav>
      </div>
    </header>
  );
}
