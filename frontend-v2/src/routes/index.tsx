import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Navigate } from "@tanstack/react-router";

import { fetchOrganizations } from "@/lib/api/organizations";
import { useAuth0 } from "@/lib/auth-provider";
import { generateOrgSlug, getPrimaryOrg } from "@/lib/org-utils";
import { queryKeys } from "@/lib/query-keys";

export const Route = createFileRoute("/")({
  component: RootRedirect,
});

function RootRedirect() {
  const { getAccessTokenSilently } = useAuth0();

  const { data: organizations, isLoading } = useQuery({
    queryKey: queryKeys.organizations.all,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizations(token);
    },
  });

  if (isLoading || !organizations) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" />
          <p className="text-muted-foreground text-sm">
            Loading organizations...
          </p>
        </div>
      </div>
    );
  }

  if (organizations.length === 0) {
    return <Navigate to="/onboarding" replace />;
  }

  const primaryOrg = getPrimaryOrg(organizations);
  if (primaryOrg) {
    return (
      <Navigate
        to="/$orgSlug"
        params={{ orgSlug: generateOrgSlug(primaryOrg) }}
        replace
      />
    );
  }

  return (
    <div className="flex h-full items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" />
        <p className="text-muted-foreground text-sm">Redirecting...</p>
      </div>
    </div>
  );
}
