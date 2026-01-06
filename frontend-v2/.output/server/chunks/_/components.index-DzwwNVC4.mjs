import { jsxs, jsx } from "react/jsx-runtime";
import { Link } from "@tanstack/react-router";
import { u as uiComponents, P as Package } from "./components.gen-2SPXrlVv.mjs";
import { C as Card, a as CardHeader, b as CardTitle, c as CardContent, d as CardDescription } from "./card-DGG0csos.mjs";
import { B as Badge } from "./badge-B1TPqLQ8.mjs";
import { A as ArrowRight } from "./arrow-right.mjs";
import "./router-BGxBdlkD.mjs";
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
function ComponentCard({
  component
}) {
  const displayName = toDisplayName(component.name);
  return /* @__PURE__ */ jsx(Link, { to: "/components/$componentName", params: {
    componentName: component.name
  }, className: "group block", children: /* @__PURE__ */ jsxs(Card, { className: "hover:border-primary/50 h-full transition-all duration-300 hover:shadow-md", children: [
    /* @__PURE__ */ jsxs(CardHeader, { children: [
      /* @__PURE__ */ jsxs("div", { className: "flex items-start justify-between", children: [
        /* @__PURE__ */ jsx("div", { className: "bg-muted rounded-lg p-3", children: /* @__PURE__ */ jsx(Package, { className: "text-primary h-6 w-6" }) }),
        /* @__PURE__ */ jsx(Badge, { variant: "secondary", children: ".tsx" })
      ] }),
      /* @__PURE__ */ jsxs(CardTitle, { className: "flex items-center gap-2", children: [
        displayName,
        /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4 opacity-0 transition-all group-hover:translate-x-1 group-hover:opacity-100" })
      ] })
    ] }),
    /* @__PURE__ */ jsx(CardContent, { children: /* @__PURE__ */ jsx(CardDescription, { className: "truncate font-mono", title: component.path, children: component.path }) })
  ] }) });
}
function ComponentsIndexPage() {
  return /* @__PURE__ */ jsxs("div", { className: "p-8", children: [
    /* @__PURE__ */ jsxs("div", { className: "mb-8", children: [
      /* @__PURE__ */ jsx("h1", { className: "text-foreground mb-2 text-3xl font-bold", children: "All Components" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "Browse and explore all available UI components. Click on a component to see its variants and usage examples." })
    ] }),
    uiComponents.length > 0 ? /* @__PURE__ */ jsx("div", { className: "grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3", children: uiComponents.map((component) => /* @__PURE__ */ jsx(ComponentCard, { component }, component.name)) }) : /* @__PURE__ */ jsxs("div", { className: "py-20 text-center", children: [
      /* @__PURE__ */ jsx("div", { className: "bg-muted mb-4 inline-flex h-16 w-16 items-center justify-center rounded-full", children: /* @__PURE__ */ jsx(Package, { className: "text-muted-foreground h-8 w-8" }) }),
      /* @__PURE__ */ jsx("h3", { className: "text-foreground mb-2 text-xl font-semibold", children: "No components found" }),
      /* @__PURE__ */ jsxs("p", { className: "text-muted-foreground mx-auto max-w-md", children: [
        "Add components to",
        " ",
        /* @__PURE__ */ jsx("code", { className: "bg-muted text-primary rounded px-2 py-0.5 text-sm", children: "src/components/ui/" }),
        " ",
        "and they will appear here automatically."
      ] })
    ] })
  ] });
}
export {
  ComponentsIndexPage as component
};
