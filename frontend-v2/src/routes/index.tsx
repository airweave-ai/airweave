/**
 * Root index route - redirects to primary organization
 */

import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

import { fetchOrganizations } from "@/lib/api/organizations";
import { useAuth0 } from "@/lib/auth-provider";
import { generateOrgSlug, getPrimaryOrg } from "@/lib/org-utils";

export const Route = createFileRoute("/")({
  component: RootRedirect,
});

function RootRedirect() {
  const { getAccessTokenSilently } = useAuth0();
  const navigate = useNavigate();

  const { data: organizations, isLoading } = useQuery({
    queryKey: ["organizations"],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizations(token);
    },
  });

  useEffect(() => {
    if (isLoading || !organizations) return;

    if (organizations.length === 0) {
      // No organizations - redirect to onboarding
      navigate({
        to: "/onboarding",
        replace: true,
      });
      return;
    }

    const primaryOrg = getPrimaryOrg(organizations);
    if (primaryOrg) {
      navigate({
        to: "/$orgSlug",
        params: { orgSlug: generateOrgSlug(primaryOrg) },
        replace: true,
      });
    }
  }, [organizations, isLoading, navigate]);

  // Show loading while fetching organizations
  return (
    <div className="flex h-full items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" />
        <p className="text-muted-foreground text-sm">
          Loading organizations...
        </p>
      </div>
    </div>
  );
}
