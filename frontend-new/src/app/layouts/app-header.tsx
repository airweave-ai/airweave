import { Fragment } from 'react';
import { IconBrandGithub } from '@tabler/icons-react';
import { Link, useMatches } from '@tanstack/react-router';
import { ChevronsUpDown } from 'lucide-react';
import type { BreadcrumbResolverMatch } from '@/app/router/breadcrumbs';
import {
  OrganizationSwitcher,
  OrganizationSwitcherMenu,
  OrganizationSwitcherTrigger,
} from '@/features/organizations';
import { useAppSession } from '@/shared/session';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
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
  const routeBreadcrumbs = useMatches({
    select: (matches) =>
      matches.flatMap((match) => {
        const breadcrumb = match.staticData.breadcrumb;

        if (!breadcrumb) {
          return [];
        }

        const breadcrumbMatch: BreadcrumbResolverMatch = {
          id: match.id,
          pathname: match.pathname,
          params: match.params as Record<string, string>,
          loaderData: match.loaderData,
        };
        const resolvedBreadcrumb =
          typeof breadcrumb === 'function'
            ? breadcrumb(breadcrumbMatch)
            : breadcrumb;

        if (!resolvedBreadcrumb) {
          return [];
        }

        const labels = Array.isArray(resolvedBreadcrumb)
          ? resolvedBreadcrumb
          : [resolvedBreadcrumb];

        return labels.map((label, index) => ({
          id: `${match.id}:${index}`,
          label,
          path: match.pathname,
        }));
      }),
  });

  return (
    <header className="border-b bg-background px-4 py-3 sm:px-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="md:hidden" />

          <Breadcrumb>
            <BreadcrumbList className="gap-1.5">
              <BreadcrumbItem className="shrink-0">
                <BreadcrumbLink asChild>
                  <Button variant="ghost" size="icon" className="-mx-1" asChild>
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
                      className="-mx-1 gap-1 text-sm font-normal text-muted-foreground"
                      type="button"
                      variant="ghost"
                      size="sm"
                    >
                      <LogoMark className="size-3 rounded-xs" />
                      <span className="truncate">
                        {currentOrganization.name}
                      </span>
                      <ChevronsUpDown
                        className="size-3.5 shrink-0"
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

              {routeBreadcrumbs.map((crumb, index) => {
                const isLast = index === routeBreadcrumbs.length - 1;

                return (
                  <Fragment key={crumb.id}>
                    <BreadcrumbSeparator className="text-foreground/20">
                      <span>/</span>
                    </BreadcrumbSeparator>

                    <BreadcrumbItem className="min-w-0">
                      {isLast ? (
                        <BreadcrumbPage className="truncate">
                          {crumb.label}
                        </BreadcrumbPage>
                      ) : (
                        <BreadcrumbLink asChild>
                          <Link className="truncate" to={crumb.path}>
                            {crumb.label}
                          </Link>
                        </BreadcrumbLink>
                      )}
                    </BreadcrumbItem>
                  </Fragment>
                );
              })}
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
