import { jsxs, jsx } from "react/jsx-runtime";
import { Link, Outlet } from "@tanstack/react-router";
import { u as uiComponents, P as Package } from "./components.gen-2SPXrlVv.mjs";
import { L as Layers } from "./layers.mjs";
import { i as ChevronRight } from "./router-BGxBdlkD.mjs";
import "@tanstack/react-query";
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
function toDisplayName(name) {
  return name.split(/[-_]/).map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
}
function ComponentsLayout() {
  return /* @__PURE__ */ jsxs("div", { className: "bg-background flex min-h-screen", children: [
    /* @__PURE__ */ jsx("aside", { className: "bg-sidebar w-64 flex-shrink-0 border-r", children: /* @__PURE__ */ jsxs("div", { className: "sticky top-0 h-screen overflow-y-auto", children: [
      /* @__PURE__ */ jsx("div", { className: "border-b p-4", children: /* @__PURE__ */ jsxs(Link, { to: "/components", className: "text-sidebar-foreground hover:text-sidebar-primary flex items-center gap-3 transition-colors", children: [
        /* @__PURE__ */ jsx("div", { className: "bg-sidebar-accent rounded-lg p-2", children: /* @__PURE__ */ jsx(Layers, { className: "text-sidebar-primary h-5 w-5" }) }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h2", { className: "font-semibold", children: "UI Components" }),
          /* @__PURE__ */ jsxs("p", { className: "text-muted-foreground text-xs", children: [
            uiComponents.length,
            " component",
            uiComponents.length !== 1 ? "s" : ""
          ] })
        ] })
      ] }) }),
      /* @__PURE__ */ jsx("nav", { className: "p-2", children: /* @__PURE__ */ jsx("ul", { className: "space-y-1", children: uiComponents.map((component) => /* @__PURE__ */ jsx("li", { children: /* @__PURE__ */ jsxs(Link, { to: "/components/$componentName", params: {
        componentName: component.name
      }, className: "group text-muted-foreground hover:text-foreground hover:bg-accent flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all", activeProps: {
        className: "bg-sidebar-accent text-sidebar-primary border border-sidebar-border"
      }, children: [
        /* @__PURE__ */ jsx(Package, { className: "h-4 w-4 flex-shrink-0" }),
        /* @__PURE__ */ jsx("span", { className: "flex-1 truncate font-medium", children: toDisplayName(component.name) }),
        /* @__PURE__ */ jsx(ChevronRight, { className: "h-4 w-4 opacity-0 transition-opacity group-hover:opacity-100" })
      ] }) }, component.name)) }) }),
      /* @__PURE__ */ jsx("div", { className: "mt-auto border-t p-4", children: /* @__PURE__ */ jsxs("p", { className: "text-muted-foreground text-center text-xs", children: [
        "Auto-generated from",
        " ",
        /* @__PURE__ */ jsx("code", { className: "text-muted-foreground", children: "components.gen.ts" })
      ] }) })
    ] }) }),
    /* @__PURE__ */ jsx("main", { className: "flex-1 overflow-y-auto", children: /* @__PURE__ */ jsx(Outlet, {}) })
  ] });
}
export {
  ComponentsLayout as component
};
