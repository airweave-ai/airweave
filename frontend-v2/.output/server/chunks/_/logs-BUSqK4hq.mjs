import { jsx, jsxs } from "react/jsx-runtime";
import { E as EmptyState } from "./empty-state-BldPO3ai.mjs";
import { I as Input } from "./input-CQnbKF5R.mjs";
import { a9 as usePageHeader, aa as useRightSidebarContent, ac as Terminal, A as Search } from "./router-BGxBdlkD.mjs";
import "react";
import "@tanstack/react-router";
import "@tanstack/react-query";
import "@tanstack/react-query-persist-client";
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
function LogsDocs() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "Sync Logs" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "View and monitor all synchronization activity across your collections and source connections." }),
    /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
      /* @__PURE__ */ jsx("h4", { className: "text-sm font-medium", children: "Log Types" }),
      /* @__PURE__ */ jsxs("ul", { className: "text-muted-foreground space-y-1 text-sm", children: [
        /* @__PURE__ */ jsx("li", { children: "Sync started/completed events" }),
        /* @__PURE__ */ jsx("li", { children: "Entity processing details" }),
        /* @__PURE__ */ jsx("li", { children: "Error and warning messages" }),
        /* @__PURE__ */ jsx("li", { children: "Performance metrics" })
      ] })
    ] })
  ] });
}
function LogsCode() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "Logs API" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Access logs programmatically:" }),
    /* @__PURE__ */ jsx("pre", { className: "bg-muted overflow-auto rounded-lg p-3 text-xs", children: /* @__PURE__ */ jsx("code", { children: `// Get sync job status
const job = await client.syncJobs.get(jobId);

console.log(job.status);
console.log(job.entities_processed);
console.log(job.started_at);
console.log(job.completed_at);` }) })
  ] });
}
function LogsHelp() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "Understanding Logs" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Logs help you track the health and status of your data synchronization." }),
    /* @__PURE__ */ jsxs("div", { className: "bg-muted rounded-lg p-3", children: [
      /* @__PURE__ */ jsx("h4", { className: "text-sm font-medium", children: "Tip" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground mt-1 text-xs", children: "Use filters to narrow down logs by collection, source, or time range." })
    ] })
  ] });
}
function LogsPage() {
  usePageHeader({
    title: "Logs",
    description: "Monitor synchronization activity",
    actions: /* @__PURE__ */ jsxs("div", { className: "relative w-64", children: [
      /* @__PURE__ */ jsx(Search, { className: "text-muted-foreground absolute top-2.5 left-2.5 size-4" }),
      /* @__PURE__ */ jsx(Input, { placeholder: "Search logs...", className: "pl-9" })
    ] })
  });
  useRightSidebarContent({
    docs: /* @__PURE__ */ jsx(LogsDocs, {}),
    code: /* @__PURE__ */ jsx(LogsCode, {}),
    help: /* @__PURE__ */ jsx(LogsHelp, {})
  });
  return /* @__PURE__ */ jsx("div", { className: "p-6", children: /* @__PURE__ */ jsx(EmptyState, { icon: /* @__PURE__ */ jsx(Terminal, {}), title: "No logs yet", description: "Logs will appear here once you start syncing data from your connected sources." }) });
}
export {
  LogsPage as component
};
