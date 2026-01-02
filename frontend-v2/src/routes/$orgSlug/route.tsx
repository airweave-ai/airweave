/**
 * Organization-scoped layout route
 *
 * This is a layout route that wraps all org-scoped pages.
 * The OrgProvider validates the slug and provides org context.
 * The OrgDataPreloader prefetches commonly needed data in the background.
 */

import { createFileRoute, Outlet } from "@tanstack/react-router";

import { LoadingState } from "@/components/ui/loading-state";
import { OrgProvider, useOrg } from "@/lib/org-context";
import { OrgDataPreloader } from "@/lib/org-data-preloader";

export const Route = createFileRoute("/$orgSlug")({
  component: OrgLayout,
});

function OrgLayout() {
  return (
    <OrgProvider>
      <OrgLayoutContent />
    </OrgProvider>
  );
}

/**
 * Inner component that checks loading state.
 * Must be inside OrgProvider to use useOrg hook.
 */
function OrgLayoutContent() {
  const { organization, isLoading } = useOrg();

  // Show loading state while organization data is being fetched
  if (isLoading || !organization) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <LoadingState />
      </div>
    );
  }

  return (
    <>
      <OrgDataPreloader />
      <Outlet />
    </>
  );
}
