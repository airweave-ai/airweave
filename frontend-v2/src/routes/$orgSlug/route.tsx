/**
 * Organization-scoped layout route
 *
 * This is a layout route that wraps all org-scoped pages.
 * The OrgProvider validates the slug and provides org context.
 */

import { createFileRoute, Outlet } from "@tanstack/react-router";

import { OrgProvider } from "@/lib/org-context";

export const Route = createFileRoute("/$orgSlug")({
  component: OrgLayout,
});

function OrgLayout() {
  return (
    <OrgProvider>
      <Outlet />
    </OrgProvider>
  );
}
