import { jsx, jsxs } from "react/jsx-runtime";
import { a9 as usePageHeader, aa as useRightSidebarContent, B as Button, P as Plus, ab as Webhook } from "./router-BGxBdlkD.mjs";
import { E as EmptyState } from "./empty-state-BldPO3ai.mjs";
import "@tanstack/react-router";
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
function WebhooksDocs() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "Webhooks" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Webhooks allow you to receive real-time notifications when events occur in your Airweave account." }),
    /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
      /* @__PURE__ */ jsx("h4", { className: "text-sm font-medium", children: "Supported Events" }),
      /* @__PURE__ */ jsxs("ul", { className: "text-muted-foreground space-y-1 text-sm", children: [
        /* @__PURE__ */ jsx("li", { children: "Sync completed" }),
        /* @__PURE__ */ jsx("li", { children: "Sync failed" }),
        /* @__PURE__ */ jsx("li", { children: "New entities added" }),
        /* @__PURE__ */ jsx("li", { children: "Connection status changed" })
      ] })
    ] })
  ] });
}
function WebhooksCode() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "Webhook Payload" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Example webhook payload structure:" }),
    /* @__PURE__ */ jsx("pre", { className: "bg-muted overflow-auto rounded-lg p-3 text-xs", children: /* @__PURE__ */ jsx("code", { children: `{
  "event": "sync.completed",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "collection_id": "col_abc123",
    "source_connection_id": "src_xyz789",
    "entities_processed": 150,
    "duration_ms": 4500
  }
}` }) })
  ] });
}
function WebhooksHelp() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "Setting Up Webhooks" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Webhooks are HTTP callbacks that receive POST requests when events occur." }),
    /* @__PURE__ */ jsxs("div", { className: "bg-muted rounded-lg p-3", children: [
      /* @__PURE__ */ jsx("h4", { className: "text-sm font-medium", children: "Requirements" }),
      /* @__PURE__ */ jsxs("ul", { className: "text-muted-foreground mt-1 space-y-1 text-xs", children: [
        /* @__PURE__ */ jsx("li", { children: "HTTPS endpoint required" }),
        /* @__PURE__ */ jsx("li", { children: "Must respond with 2xx status" }),
        /* @__PURE__ */ jsx("li", { children: "Timeout: 30 seconds" })
      ] })
    ] })
  ] });
}
function WebhooksPage() {
  usePageHeader({
    title: "Webhooks",
    description: "Receive real-time event notifications",
    actions: /* @__PURE__ */ jsxs(Button, { children: [
      /* @__PURE__ */ jsx(Plus, { className: "mr-2 size-4" }),
      "Create Webhook"
    ] })
  });
  useRightSidebarContent({
    docs: /* @__PURE__ */ jsx(WebhooksDocs, {}),
    code: /* @__PURE__ */ jsx(WebhooksCode, {}),
    help: /* @__PURE__ */ jsx(WebhooksHelp, {})
  });
  return /* @__PURE__ */ jsx("div", { className: "p-6", children: /* @__PURE__ */ jsx(EmptyState, { icon: /* @__PURE__ */ jsx(Webhook, {}), title: "Add your first webhook", description: "Get notified when sync jobs complete, fail, or when new data is available.", children: /* @__PURE__ */ jsxs(Button, { variant: "outline", children: [
    /* @__PURE__ */ jsx(Plus, { className: "mr-2 size-4" }),
    "Create Webhook"
  ] }) }) });
}
export {
  WebhooksPage as component
};
