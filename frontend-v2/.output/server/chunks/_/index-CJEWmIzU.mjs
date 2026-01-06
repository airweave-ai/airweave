import { jsx, jsxs } from "react/jsx-runtime";
import { useQuery } from "@tanstack/react-query";
import { Navigate } from "@tanstack/react-router";
import { u as useAuth0, q as queryKeys, f as fetchOrganizations, o as getPrimaryOrg, g as generateOrgSlug } from "./router-BGxBdlkD.mjs";
import "@tanstack/react-query-persist-client";
import "react";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "clsx";
import "tailwind-merge";
import "@radix-ui/react-dialog";
import "@radix-ui/react-tooltip";
import "zustand";
import "zustand/middleware";
import "@radix-ui/react-avatar";
import "@radix-ui/react-dropdown-menu";
import "cmdk";
import "sonner";
import "idb-keyval";
function RootRedirect() {
  const {
    getAccessTokenSilently
  } = useAuth0();
  const {
    data: organizations,
    isLoading
  } = useQuery({
    queryKey: queryKeys.organizations.all,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizations(token);
    }
  });
  if (isLoading || !organizations) {
    return /* @__PURE__ */ jsx("div", { className: "flex h-full items-center justify-center", children: /* @__PURE__ */ jsxs("div", { className: "flex flex-col items-center gap-4", children: [
      /* @__PURE__ */ jsx("div", { className: "border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Loading organizations..." })
    ] }) });
  }
  if (organizations.length === 0) {
    return /* @__PURE__ */ jsx(Navigate, { to: "/onboarding", replace: true });
  }
  const primaryOrg = getPrimaryOrg(organizations);
  if (primaryOrg) {
    return /* @__PURE__ */ jsx(Navigate, { to: "/$orgSlug", params: {
      orgSlug: generateOrgSlug(primaryOrg)
    }, replace: true });
  }
  return /* @__PURE__ */ jsx("div", { className: "flex h-full items-center justify-center", children: /* @__PURE__ */ jsxs("div", { className: "flex flex-col items-center gap-4", children: [
    /* @__PURE__ */ jsx("div", { className: "border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Redirecting..." })
  ] }) });
}
export {
  RootRedirect as component
};
