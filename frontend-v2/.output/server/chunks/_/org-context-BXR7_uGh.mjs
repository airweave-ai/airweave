import { jsx } from "react/jsx-runtime";
import { useQuery } from "@tanstack/react-query";
import { useParams, Navigate } from "@tanstack/react-router";
import { useMemo, createContext, useContext } from "react";
import { u as useAuth0, q as queryKeys, f as fetchOrganizations, ar as findOrgBySlug, o as getPrimaryOrg, g as generateOrgSlug } from "./router-BGxBdlkD.mjs";
const OrgContext = createContext(null);
function OrgProvider({ children }) {
  const { getAccessTokenSilently } = useAuth0();
  const params = useParams({ strict: false });
  const orgSlug = params.orgSlug;
  const {
    data: organizations = [],
    isLoading,
    error
  } = useQuery({
    queryKey: queryKeys.organizations.all,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizations(token);
    },
    staleTime: 1e3 * 60 * 5
  });
  const organization = useMemo(() => {
    if (!orgSlug || organizations.length === 0) return null;
    return findOrgBySlug(organizations, orgSlug) ?? null;
  }, [orgSlug, organizations]);
  const redirect = useMemo(() => {
    if (isLoading || organizations.length === 0) return null;
    if (!orgSlug) {
      const primaryOrg = getPrimaryOrg(organizations);
      if (primaryOrg) {
        return {
          to: "/$orgSlug",
          params: { orgSlug: generateOrgSlug(primaryOrg) }
        };
      }
      return null;
    }
    if (!organization) {
      const primaryOrg = getPrimaryOrg(organizations);
      if (primaryOrg) {
        return {
          to: "/$orgSlug",
          params: { orgSlug: generateOrgSlug(primaryOrg) }
        };
      }
      return null;
    }
    const canonicalSlug = generateOrgSlug(organization);
    if (orgSlug !== canonicalSlug) {
      const currentPath = typeof window !== "undefined" ? window.location.pathname : "";
      const restOfPath = currentPath.replace(`/${orgSlug}`, "");
      return {
        to: `/$orgSlug${restOfPath}`,
        params: { orgSlug: canonicalSlug }
      };
    }
    return null;
  }, [orgSlug, organization, organizations, isLoading]);
  const value = useMemo(
    () => ({
      organization,
      organizations,
      isLoading,
      error,
      getOrgSlug: generateOrgSlug
    }),
    [organization, organizations, isLoading, error]
  );
  if (redirect) {
    return /* @__PURE__ */ jsx(Navigate, { to: redirect.to, params: redirect.params, replace: true });
  }
  return /* @__PURE__ */ jsx(OrgContext.Provider, { value, children });
}
function useOrg() {
  const context = useContext(OrgContext);
  if (!context) {
    throw new Error("useOrg must be used within an OrgProvider");
  }
  return context;
}
export {
  OrgProvider as O,
  useOrg as u
};
