/**
 * Organization context for URL-based multi-tenancy
 *
 * Provides the current organization based on URL slug to all child components.
 */

import { useQuery } from "@tanstack/react-query";
import { Navigate, useParams } from "@tanstack/react-router";
import { createContext, ReactNode, useContext, useMemo } from "react";

import { fetchOrganizations, type Organization } from "./api/organizations";
import { useAuth0 } from "./auth-provider";
import { findOrgBySlug, generateOrgSlug, getPrimaryOrg } from "./org-utils";
import { queryKeys } from "./query-keys";

interface OrgContextValue {
  /** Current organization based on URL */
  organization: Organization | null;
  /** All organizations the user has access to */
  organizations: Organization[];
  /** Whether organizations are loading */
  isLoading: boolean;
  /** Error if organizations failed to load */
  error: Error | null;
  /** Generate URL slug for an organization */
  getOrgSlug: (org: Organization) => string;
}

const OrgContext = createContext<OrgContextValue | null>(null);

interface OrgProviderProps {
  children: ReactNode;
}

/**
 * Provider for organization context within org-scoped routes
 * Reads the orgSlug from URL params and validates against user's organizations
 */
export function OrgProvider({ children }: OrgProviderProps) {
  const { getAccessTokenSilently } = useAuth0();
  const params = useParams({ strict: false }) as { orgSlug?: string };
  const orgSlug = params.orgSlug;

  // Fetch organizations using React Query
  const {
    data: organizations = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: queryKeys.organizations.all,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizations(token);
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // Find the current organization based on URL slug
  const organization = useMemo(() => {
    if (!orgSlug || organizations.length === 0) return null;
    return findOrgBySlug(organizations, orgSlug) ?? null;
  }, [orgSlug, organizations]);

  // Handle redirects during render (no useEffect needed)
  const redirect = useMemo(() => {
    if (isLoading || organizations.length === 0) return null;

    // If no orgSlug in URL, redirect to primary org
    if (!orgSlug) {
      const primaryOrg = getPrimaryOrg(organizations);
      if (primaryOrg) {
        return {
          to: "/$orgSlug" as const,
          params: { orgSlug: generateOrgSlug(primaryOrg) },
        };
      }
      return null;
    }

    // If org not found, redirect to primary org
    if (!organization) {
      const primaryOrg = getPrimaryOrg(organizations);
      if (primaryOrg) {
        return {
          to: "/$orgSlug" as const,
          params: { orgSlug: generateOrgSlug(primaryOrg) },
        };
      }
      return null;
    }

    // If slug is not canonical, redirect to canonical URL
    const canonicalSlug = generateOrgSlug(organization);
    if (orgSlug !== canonicalSlug) {
      // Preserve the rest of the path
      const currentPath =
        typeof window !== "undefined" ? window.location.pathname : "";
      const restOfPath = currentPath.replace(`/${orgSlug}`, "");
      return {
        to: `/$orgSlug${restOfPath}` as "/$orgSlug",
        params: { orgSlug: canonicalSlug },
      };
    }

    return null;
  }, [orgSlug, organization, organizations, isLoading]);

  const value = useMemo(
    () => ({
      organization,
      organizations,
      isLoading,
      error: error as Error | null,
      getOrgSlug: generateOrgSlug,
    }),
    [organization, organizations, isLoading, error]
  );

  // Perform redirect if needed (using Navigate component instead of useEffect)
  if (redirect) {
    return <Navigate to={redirect.to} params={redirect.params} replace />;
  }

  return <OrgContext.Provider value={value}>{children}</OrgContext.Provider>;
}

/**
 * Hook to access organization context
 * Must be used within an OrgProvider
 */
export function useOrg(): OrgContextValue {
  const context = useContext(OrgContext);
  if (!context) {
    throw new Error("useOrg must be used within an OrgProvider");
  }
  return context;
}

/**
 * Hook to get the current organization (throws if not available)
 */
export function useCurrentOrg(): Organization {
  const { organization, isLoading } = useOrg();
  if (isLoading) {
    throw new Error("Organization is still loading");
  }
  if (!organization) {
    throw new Error("No organization found");
  }
  return organization;
}
