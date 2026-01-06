import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import { useQueryClient, useQuery, useMutation } from "@tanstack/react-query";
import { useNavigate, useLocation } from "@tanstack/react-router";
import React__default, { useState, useRef, useMemo, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { E as ErrorState, C as Copy, A as AlertDialog, b as AlertDialogContent, c as AlertDialogHeader, d as AlertDialogTitle, e as AlertDialogDescription, i as CircleAlert, f as AlertDialogFooter, g as AlertDialogCancel, h as AlertDialogAction } from "./error-state-BYmPP-hR.mjs";
import { L as LoadingState } from "./loading-state-CJE8ekwd.mjs";
import { c as createLucideIcon, u as useAuth0, am as Route, q as queryKeys, a9 as usePageHeader, aa as useRightSidebarContent, af as API_BASE_URL, ag as getAuthHeaders, ah as parseErrorResponse, B as Button, h as Check, an as TooltipProvider, T as Tooltip, p as TooltipTrigger, r as TooltipContent, a as cn, P as Plus, ae as TriangleAlert, L as LoaderCircle, D as Dialog, k as DialogContent, m as DialogTitle, n as DialogDescription, X, E as DropdownMenu, F as DropdownMenuTrigger, G as DropdownMenuContent, K as DropdownMenuItem, C as CodeXml, ac as Terminal, A as Search$1, ak as CircleCheck, i as ChevronRight, ao as Info, ap as CircleQuestionMark } from "./router-BGxBdlkD.mjs";
import { u as useAddSourceStore, a as fetchCollection, d as deleteCollection, L as Label } from "./collections-Bp-yOdLv.mjs";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { I as Input } from "./input-CQnbKF5R.mjs";
import { u as useIsDark } from "./use-is-dark-CmoXbbju.mjs";
import { b as getAppIconUrl, e as fetchSource, f as fetchSources, h as CollectionDetailHelp, i as CollectionDetailCode, j as CollectionDetailDocs } from "./sidebar-content-DdEgH4En.mjs";
import { u as useOrg } from "./org-context-BXR7_uGh.mjs";
import { E as EmptyState } from "./empty-state-BldPO3ai.mjs";
import { u as useKeyboardShortcut } from "./use-keyboard-shortcut-fo-gRryO.mjs";
import { P as Pencil, T as Trash, E as ExternalLink, L as Link } from "./trash.mjs";
import { C as ChevronDown } from "./use-docs-content-CQG4H0bA.mjs";
import { T as Trash2 } from "./trash-2.mjs";
import { S as Settings, F as FileText, M as MessageSquare, A as ArrowLeft } from "./settings.mjs";
import { L as Layers } from "./layers.mjs";
import { A as ArrowRight } from "./arrow-right.mjs";
import "@radix-ui/react-alert-dialog";
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
import "idb-keyval";
const __iconNode$i = [
  ["path", { d: "m5 12 7-7 7 7", key: "hav0vg" }],
  ["path", { d: "M12 19V5", key: "x0mq9r" }]
];
const ArrowUp = createLucideIcon("arrow-up", __iconNode$i);
const __iconNode$h = [
  ["circle", { cx: "7.5", cy: "7.5", r: ".5", fill: "currentColor", key: "kqv944" }],
  ["circle", { cx: "18.5", cy: "5.5", r: ".5", fill: "currentColor", key: "lysivs" }],
  ["circle", { cx: "11.5", cy: "11.5", r: ".5", fill: "currentColor", key: "byv1b8" }],
  ["circle", { cx: "7.5", cy: "16.5", r: ".5", fill: "currentColor", key: "nkw3mc" }],
  ["circle", { cx: "17.5", cy: "14.5", r: ".5", fill: "currentColor", key: "1gjh6j" }],
  ["path", { d: "M3 3v16a2 2 0 0 0 2 2h16", key: "c24i48" }]
];
const ChartScatter = createLucideIcon("chart-scatter", __iconNode$h);
const __iconNode$g = [["path", { d: "m18 15-6-6-6 6", key: "153udz" }]];
const ChevronUp = createLucideIcon("chevron-up", __iconNode$g);
const __iconNode$f = [
  ["path", { d: "M21.801 10A10 10 0 1 1 17 3.335", key: "yps3ct" }],
  ["path", { d: "m9 11 3 3L22 4", key: "1pflzl" }]
];
const CircleCheckBig = createLucideIcon("circle-check-big", __iconNode$f);
const __iconNode$e = [
  ["path", { d: "M12 6v6l1.56.78", key: "14ed3g" }],
  ["path", { d: "M13.227 21.925a10 10 0 1 1 8.767-9.588", key: "jwkls1" }],
  ["path", { d: "m14 18 4-4 4 4", key: "ftkppy" }],
  ["path", { d: "M18 22v-8", key: "su0gjh" }]
];
const ClockArrowUp = createLucideIcon("clock-arrow-up", __iconNode$e);
const __iconNode$d = [
  ["path", { d: "M12 6v6l4 2", key: "mmk7yg" }],
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }]
];
const Clock = createLucideIcon("clock", __iconNode$d);
const __iconNode$c = [
  [
    "path",
    {
      d: "M10 20a1 1 0 0 0 .553.895l2 1A1 1 0 0 0 14 21v-7a2 2 0 0 1 .517-1.341L21.74 4.67A1 1 0 0 0 21 3H3a1 1 0 0 0-.742 1.67l7.225 7.989A2 2 0 0 1 10 14z",
      key: "sc7q7i"
    }
  ]
];
const Funnel = createLucideIcon("funnel", __iconNode$c);
const __iconNode$b = [
  ["circle", { cx: "18", cy: "18", r: "3", key: "1xkwt0" }],
  ["circle", { cx: "6", cy: "6", r: "3", key: "1lh9wr" }],
  ["path", { d: "M6 21V9a9 9 0 0 0 9 9", key: "7kw0sc" }]
];
const GitMerge = createLucideIcon("git-merge", __iconNode$b);
const __iconNode$a = [
  ["path", { d: "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8", key: "1357e3" }],
  ["path", { d: "M3 3v5h5", key: "1xhq8a" }],
  ["path", { d: "M12 7v5l4 2", key: "1fdv2h" }]
];
const History = createLucideIcon("history", __iconNode$a);
const __iconNode$9 = [
  ["path", { d: "M3 5h6", key: "1ltk0q" }],
  ["path", { d: "M3 12h13", key: "ppymz1" }],
  ["path", { d: "M3 19h13", key: "bpdczq" }],
  ["path", { d: "m16 8-3-3 3-3", key: "1pjpp6" }],
  ["path", { d: "M21 19V7a2 2 0 0 0-2-2h-6", key: "4zzq67" }]
];
const ListStart = createLucideIcon("list-start", __iconNode$9);
const __iconNode$8 = [
  [
    "path",
    {
      d: "M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z",
      key: "10ikf1"
    }
  ]
];
const Play = createLucideIcon("play", __iconNode$8);
const __iconNode$7 = [
  ["path", { d: "M12 22v-5", key: "1ega77" }],
  ["path", { d: "M15 8V2", key: "18g5xt" }],
  [
    "path",
    { d: "M17 8a1 1 0 0 1 1 1v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1z", key: "1xoxul" }
  ],
  ["path", { d: "M9 8V2", key: "14iosj" }]
];
const Plug = createLucideIcon("plug", __iconNode$7);
const __iconNode$6 = [
  ["path", { d: "M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8", key: "v9h5vc" }],
  ["path", { d: "M21 3v5h-5", key: "1q7to0" }],
  ["path", { d: "M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16", key: "3uifl3" }],
  ["path", { d: "M8 16H3v5", key: "1cv678" }]
];
const RefreshCw = createLucideIcon("refresh-cw", __iconNode$6);
const __iconNode$5 = [
  ["path", { d: "M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8", key: "1p45f6" }],
  ["path", { d: "M21 3v5h-5", key: "1q7to0" }]
];
const RotateCw = createLucideIcon("rotate-cw", __iconNode$5);
const __iconNode$4 = [
  ["path", { d: "m13.5 8.5-5 5", key: "1cs55j" }],
  ["path", { d: "m8.5 8.5 5 5", key: "a8mexj" }],
  ["circle", { cx: "11", cy: "11", r: "8", key: "4ej97u" }],
  ["path", { d: "m21 21-4.3-4.3", key: "1qie3q" }]
];
const SearchX = createLucideIcon("search-x", __iconNode$4);
const __iconNode$3 = [
  [
    "path",
    {
      d: "M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z",
      key: "1ffxy3"
    }
  ],
  ["path", { d: "m21.854 2.147-10.94 10.939", key: "12cjpa" }]
];
const Send = createLucideIcon("send", __iconNode$3);
const __iconNode$2 = [
  ["path", { d: "M14 17H5", key: "gfn3mx" }],
  ["path", { d: "M19 7h-9", key: "6i9tg" }],
  ["circle", { cx: "17", cy: "17", r: "3", key: "18b49y" }],
  ["circle", { cx: "7", cy: "7", r: "3", key: "dfmy0x" }]
];
const Settings2 = createLucideIcon("settings-2", __iconNode$2);
const __iconNode$1 = [
  ["rect", { width: "18", height: "18", x: "3", y: "3", rx: "2", key: "afitv7" }]
];
const Square = createLucideIcon("square", __iconNode$1);
const __iconNode = [
  ["path", { d: "M12 4v16", key: "1654pz" }],
  ["path", { d: "M4 7V5a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v2", key: "e0r10z" }],
  ["path", { d: "M9 20h6", key: "s66wpe" }]
];
const Type = createLucideIcon("type", __iconNode);
async function createSourceConnection(token, orgId, data) {
  const response = await fetch(`${API_BASE_URL}/source-connections`, {
    method: "POST",
    headers: getAuthHeaders(token, orgId),
    body: JSON.stringify(data)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create source connection"
    );
    throw new Error(message);
  }
  return response.json();
}
async function fetchSourceConnections(token, orgId, collectionId) {
  const response = await fetch(
    `${API_BASE_URL}/source-connections/?collection=${collectionId}`,
    {
      headers: getAuthHeaders(token, orgId)
    }
  );
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch source connections"
    );
    throw new Error(message);
  }
  return response.json();
}
async function fetchSourceConnection(token, orgId, id, regenerateAuthUrl = false) {
  const url = regenerateAuthUrl ? `${API_BASE_URL}/source-connections/${id}?regenerate_auth_url=true` : `${API_BASE_URL}/source-connections/${id}`;
  const response = await fetch(url, {
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch source connection"
    );
    throw new Error(message);
  }
  return response.json();
}
async function runSourceConnectionSync(token, orgId, id) {
  const response = await fetch(`${API_BASE_URL}/source-connections/${id}/run`, {
    method: "POST",
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(response, "Failed to start sync");
    throw new Error(message);
  }
  return response.json();
}
async function cancelSourceConnectionSync(token, orgId, connectionId, jobId) {
  const response = await fetch(
    `${API_BASE_URL}/source-connections/${connectionId}/jobs/${jobId}/cancel`,
    {
      method: "POST",
      headers: getAuthHeaders(token, orgId)
    }
  );
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to cancel sync job"
    );
    throw new Error(message);
  }
}
async function deleteSourceConnection(token, orgId, id) {
  const response = await fetch(`${API_BASE_URL}/source-connections/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to delete source connection"
    );
    throw new Error(message);
  }
}
function SourceAuthenticationView({
  sourceName,
  sourceShortName,
  authenticationUrl,
  onRefreshUrl,
  isRefreshing,
  onDelete,
  className
}) {
  const iconUrl = getAppIconUrl(sourceShortName);
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-6",
        className
      ),
      children: /* @__PURE__ */ jsxs("div", { className: "flex flex-col items-center text-center", children: [
        /* @__PURE__ */ jsx("div", { className: "bg-background mb-4 flex size-16 items-center justify-center overflow-hidden rounded-lg border p-2", children: /* @__PURE__ */ jsx(
          "img",
          {
            src: iconUrl,
            alt: sourceName,
            className: "size-full object-contain"
          }
        ) }),
        /* @__PURE__ */ jsxs("h3", { className: "mb-2 text-lg font-semibold", children: [
          "Connect to ",
          sourceName
        ] }),
        /* @__PURE__ */ jsxs("p", { className: "text-muted-foreground mb-6 max-w-md text-sm", children: [
          "This source requires authentication. Click the button below to authorize access to your ",
          sourceName,
          " data."
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex flex-wrap items-center justify-center gap-3", children: [
          authenticationUrl ? /* @__PURE__ */ jsx(Button, { asChild: true, children: /* @__PURE__ */ jsxs(
            "a",
            {
              href: authenticationUrl,
              target: "_blank",
              rel: "noopener noreferrer",
              children: [
                /* @__PURE__ */ jsx(ExternalLink, { className: "mr-2 size-4" }),
                "Authenticate with ",
                sourceName
              ]
            }
          ) }) : /* @__PURE__ */ jsxs(Button, { disabled: true, children: [
            /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 size-4 animate-spin" }),
            "Generating auth URL..."
          ] }),
          onRefreshUrl && /* @__PURE__ */ jsxs(
            Button,
            {
              variant: "outline",
              onClick: onRefreshUrl,
              disabled: isRefreshing,
              children: [
                isRefreshing ? /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 size-4 animate-spin" }) : /* @__PURE__ */ jsx(RefreshCw, { className: "mr-2 size-4" }),
                "Refresh URL"
              ]
            }
          ),
          onDelete && /* @__PURE__ */ jsxs(
            Button,
            {
              variant: "outline",
              onClick: onDelete,
              className: "text-destructive hover:bg-destructive/10 hover:text-destructive",
              children: [
                /* @__PURE__ */ jsx(Trash2, { className: "mr-2 size-4" }),
                "Remove"
              ]
            }
          )
        ] })
      ] })
    }
  );
}
function ConfigFields({ fields, values, onChange }) {
  const hasRequiredFields = fields.some((f) => f.required);
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsxs(Label, { className: "text-xs tracking-wider text-gray-500 uppercase dark:text-gray-400", children: [
      "Additional Configuration",
      !hasRequiredFields && " (optional)"
    ] }),
    fields.map((field) => /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
      /* @__PURE__ */ jsxs(Label, { className: "text-sm font-medium", children: [
        field.display_name || field.name,
        field.required && /* @__PURE__ */ jsx("span", { className: "ml-1 text-red-500", children: "*" })
      ] }),
      field.description && /* @__PURE__ */ jsx("p", { className: "text-xs text-gray-400 dark:text-gray-500", children: field.description }),
      /* @__PURE__ */ jsx(
        Input,
        {
          value: Array.isArray(values[field.name]) ? values[field.name].join(", ") : values[field.name] || "",
          onChange: (e) => onChange(field.name, e.target.value),
          className: "border-gray-200 bg-white placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:placeholder:text-gray-500"
        }
      )
    ] }, field.name))
  ] });
}
function isSensitiveField(name) {
  return ["password", "token", "secret", "key"].some(
    (s) => name.toLowerCase().includes(s)
  );
}
function DirectAuthFields({
  fields,
  values,
  onChange
}) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx(Label, { className: "text-xs tracking-wider text-gray-500 uppercase dark:text-gray-400", children: "Credentials" }),
    fields.map((field) => /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
      /* @__PURE__ */ jsxs(Label, { className: "text-sm font-medium", children: [
        field.display_name || field.name,
        field.required && /* @__PURE__ */ jsx("span", { className: "ml-1 text-red-500", children: "*" })
      ] }),
      field.description && /* @__PURE__ */ jsx("p", { className: "text-xs text-gray-400 dark:text-gray-500", children: field.description }),
      /* @__PURE__ */ jsx(
        Input,
        {
          type: isSensitiveField(field.name) ? "password" : "text",
          value: values[field.name] || "",
          onChange: (e) => onChange(field.name, e.target.value),
          className: "border-gray-200 bg-white placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:placeholder:text-gray-500"
        }
      )
    ] }, field.name))
  ] });
}
function OAuthSettings({
  sourceShortName,
  sourceName,
  requiresByoc,
  useCustomOAuth,
  clientId,
  clientSecret,
  redirectUrl,
  onUseCustomOAuthChange,
  onClientIdChange,
  onClientSecretChange
}) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    requiresByoc ? /* @__PURE__ */ jsx(
      ByocOAuthFields,
      {
        sourceShortName,
        sourceName,
        clientId,
        clientSecret,
        onClientIdChange,
        onClientSecretChange
      }
    ) : /* @__PURE__ */ jsx(
      OptionalCustomOAuth,
      {
        useCustomOAuth,
        clientId,
        clientSecret,
        onUseCustomOAuthChange,
        onClientIdChange,
        onClientSecretChange
      }
    ),
    /* @__PURE__ */ jsx(RedirectUrlDisplay, { url: redirectUrl })
  ] });
}
function ByocOAuthFields({
  sourceShortName,
  sourceName,
  clientId,
  clientSecret,
  onClientIdChange,
  onClientSecretChange
}) {
  const docsUrl = `https://docs.airweave.ai/docs/connectors/${sourceShortName.replace(/_/g, "-")}`;
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400", children: [
      /* @__PURE__ */ jsx(Info, { className: "mt-0.5 h-4 w-4 flex-shrink-0" }),
      /* @__PURE__ */ jsxs("p", { className: "text-sm", children: [
        sourceName,
        " requires you to provide your own OAuth application credentials. You'll need to create an OAuth app in ",
        sourceName,
        "'s developer console."
      ] })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
      /* @__PURE__ */ jsx(CircleQuestionMark, { className: "h-4 w-4 text-gray-400 dark:text-gray-500" }),
      /* @__PURE__ */ jsx("span", { className: "text-sm text-gray-600 dark:text-gray-400", children: "Need help setting up OAuth?" }),
      /* @__PURE__ */ jsxs(
        "a",
        {
          href: docsUrl,
          target: "_blank",
          rel: "noopener noreferrer",
          className: "inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:underline dark:text-blue-400",
          children: [
            "View documentation",
            /* @__PURE__ */ jsx(ExternalLink, { className: "h-3 w-3" })
          ]
        }
      )
    ] }),
    /* @__PURE__ */ jsx(
      OAuthCredentialInputs,
      {
        clientId,
        clientSecret,
        onClientIdChange,
        onClientSecretChange,
        required: true
      }
    )
  ] });
}
function OptionalCustomOAuth({
  useCustomOAuth,
  clientId,
  clientSecret,
  onUseCustomOAuthChange,
  onClientIdChange,
  onClientSecretChange
}) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-3", children: [
    /* @__PURE__ */ jsxs("label", { className: "flex cursor-pointer items-center gap-3", children: [
      /* @__PURE__ */ jsxs("div", { className: "relative", children: [
        /* @__PURE__ */ jsx(
          "input",
          {
            type: "checkbox",
            checked: useCustomOAuth,
            onChange: (e) => onUseCustomOAuthChange(e.target.checked),
            className: "sr-only"
          }
        ),
        /* @__PURE__ */ jsx(
          "div",
          {
            className: cn(
              "h-6 w-10 rounded-full transition-colors",
              useCustomOAuth ? "bg-blue-600" : "bg-gray-200 dark:bg-gray-800"
            ),
            children: /* @__PURE__ */ jsx(
              "div",
              {
                className: cn(
                  "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform",
                  useCustomOAuth && "translate-x-4"
                )
              }
            )
          }
        )
      ] }),
      /* @__PURE__ */ jsx("span", { className: "text-sm text-gray-600 dark:text-gray-400", children: "Use custom OAuth credentials" })
    ] }),
    useCustomOAuth && /* @__PURE__ */ jsx("div", { className: "space-y-3 pl-13", children: /* @__PURE__ */ jsx(
      OAuthCredentialInputs,
      {
        clientId,
        clientSecret,
        onClientIdChange,
        onClientSecretChange
      }
    ) })
  ] });
}
function OAuthCredentialInputs({
  clientId,
  clientSecret,
  onClientIdChange,
  onClientSecretChange,
  required
}) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-3", children: [
    /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
      /* @__PURE__ */ jsxs(Label, { className: "text-sm font-medium", children: [
        "Client ID ",
        required && /* @__PURE__ */ jsx("span", { className: "text-red-500", children: "*" })
      ] }),
      /* @__PURE__ */ jsx(
        Input,
        {
          value: clientId,
          onChange: (e) => onClientIdChange(e.target.value),
          placeholder: required ? "Your OAuth Client ID" : "Client ID",
          className: "border-gray-200 bg-white placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:placeholder:text-gray-500"
        }
      )
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
      /* @__PURE__ */ jsxs(Label, { className: "text-sm font-medium", children: [
        "Client Secret ",
        required && /* @__PURE__ */ jsx("span", { className: "text-red-500", children: "*" })
      ] }),
      /* @__PURE__ */ jsx(
        Input,
        {
          type: "password",
          value: clientSecret,
          onChange: (e) => onClientSecretChange(e.target.value),
          placeholder: required ? "Your OAuth Client Secret" : "Client Secret",
          className: "border-gray-200 bg-white placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:placeholder:text-gray-500"
        }
      )
    ] })
  ] });
}
function RedirectUrlDisplay({ url }) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
      /* @__PURE__ */ jsx(Label, { className: "text-xs tracking-wider text-gray-400 uppercase dark:text-gray-500", children: "Redirect URL" }),
      /* @__PURE__ */ jsx(Info, { className: "h-3 w-3 text-gray-400 dark:text-gray-600" })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 font-mono text-xs text-gray-400 dark:border-gray-800 dark:bg-gray-900/50 dark:text-gray-500", children: url })
  ] });
}
function getDefaultRedirectUrl() {
  return `${window.location.origin}?oauth_return=true`;
}
function SourceConfigView({
  collectionId,
  collectionName,
  sourceShortName,
  sourceName,
  connectionName,
  authMode,
  authFields,
  configFields,
  useCustomOAuth,
  clientId,
  clientSecret,
  onBack,
  onConnectionNameChange,
  onAuthModeChange,
  onAuthFieldChange,
  onConfigFieldChange,
  onUseCustomOAuthChange,
  onClientIdChange,
  onClientSecretChange,
  onSuccess,
  onCancel
}) {
  const isDark = useIsDark();
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const queryClient = useQueryClient();
  const [oauthUrl, setOauthUrl] = useState(null);
  const { data: sourceDetails, isLoading: isLoadingSource } = useQuery({
    queryKey: ["source", organization?.id, sourceShortName],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSource(token, organization.id, sourceShortName);
    },
    enabled: !!organization && !!sourceShortName
  });
  const availableAuthMethods = useMemo(() => {
    if (!sourceDetails?.auth_methods) return [];
    const methods = [];
    if (sourceDetails.auth_methods.includes("direct")) {
      methods.push("direct_auth");
    }
    if (sourceDetails.auth_methods.includes("oauth_browser") || sourceDetails.auth_methods.includes("oauth_token")) {
      methods.push("oauth2");
    }
    return methods;
  }, [sourceDetails]);
  useEffect(() => {
    if (sourceDetails && !authMode && availableAuthMethods.length > 0) {
      if (availableAuthMethods.includes("direct_auth")) {
        onAuthModeChange("direct_auth");
      } else if (availableAuthMethods.includes("oauth2")) {
        onAuthModeChange("oauth2");
        if (sourceDetails.requires_byoc) {
          onUseCustomOAuthChange(true);
        }
      }
    }
  }, [
    sourceDetails,
    authMode,
    availableAuthMethods,
    onAuthModeChange,
    onUseCustomOAuthChange
  ]);
  const createMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      let authentication = {};
      if (authMode === "direct_auth") {
        authentication = { credentials: authFields };
      } else if (authMode === "oauth2") {
        authentication = {
          redirect_uri: getDefaultRedirectUrl()
        };
        if (sourceDetails?.requires_byoc || useCustomOAuth) {
          authentication.client_id = clientId;
          authentication.client_secret = clientSecret;
        }
      }
      const config = {};
      for (const [key, value] of Object.entries(configFields)) {
        if (value && (Array.isArray(value) ? value.length > 0 : value !== "")) {
          config[key] = value;
        }
      }
      return createSourceConnection(token, organization.id, {
        name: connectionName.trim(),
        description: `${sourceName} connection for ${collectionName}`,
        short_name: sourceShortName,
        readable_collection_id: collectionId,
        authentication,
        config: Object.keys(config).length > 0 ? config : void 0,
        sync_immediately: authMode === "direct_auth",
        redirect_url: getDefaultRedirectUrl()
      });
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sourceConnections.list(
          organization.id,
          collectionId
        )
      });
      const authUrl = result.auth?.auth_url;
      if (authUrl) {
        setOauthUrl(authUrl);
        onSuccess(result.id, authUrl);
      } else {
        toast.success("Source connected successfully!");
        onSuccess(result.id);
      }
    },
    onError: (error) => {
      toast.error("Failed to create connection", {
        description: error.message
      });
    }
  });
  const isFormValid = useMemo(() => {
    const trimmedName = connectionName.trim();
    if (!trimmedName || trimmedName.length < 4 || trimmedName.length > 42) {
      return false;
    }
    if (authMode === "direct_auth" && sourceDetails?.auth_fields?.fields) {
      const requiredFields = sourceDetails.auth_fields.fields.filter(
        (f) => f.required
      );
      for (const field of requiredFields) {
        if (!authFields[field.name]?.trim()) {
          return false;
        }
      }
    }
    if (authMode === "oauth2") {
      if (sourceDetails?.requires_byoc || useCustomOAuth) {
        if (!clientId.trim() || !clientSecret.trim()) {
          return false;
        }
      }
    }
    if (sourceDetails?.config_fields?.fields) {
      const requiredConfigFields = sourceDetails.config_fields.fields.filter(
        (f) => f.required
      );
      for (const field of requiredConfigFields) {
        const value = configFields[field.name];
        if (Array.isArray(value)) {
          if (value.length === 0) return false;
        } else if (!value?.trim()) {
          return false;
        }
      }
    }
    return true;
  }, [
    connectionName,
    authMode,
    authFields,
    configFields,
    sourceDetails,
    useCustomOAuth,
    clientId,
    clientSecret
  ]);
  const handleSubmit = useCallback(() => {
    if (!isFormValid) return;
    createMutation.mutate();
  }, [isFormValid, createMutation]);
  if (oauthUrl) {
    return /* @__PURE__ */ jsxs("div", { className: "flex h-full flex-col", children: [
      /* @__PURE__ */ jsx("div", { className: "flex-1 overflow-auto p-6", children: /* @__PURE__ */ jsx(
        SourceAuthenticationView,
        {
          sourceName,
          sourceShortName,
          authenticationUrl: oauthUrl
        }
      ) }),
      /* @__PURE__ */ jsx("div", { className: "border-t border-gray-200 px-6 py-4 dark:border-gray-800", children: /* @__PURE__ */ jsx(
        "button",
        {
          onClick: onCancel,
          className: "text-sm font-medium text-gray-600 transition-colors hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200",
          children: "Close"
        }
      ) })
    ] });
  }
  if (isLoadingSource) {
    return /* @__PURE__ */ jsx("div", { className: "flex h-full items-center justify-center", children: /* @__PURE__ */ jsx(LoaderCircle, { className: "text-muted-foreground h-8 w-8 animate-spin" }) });
  }
  return /* @__PURE__ */ jsxs("div", { className: "flex h-full flex-col", children: [
    /* @__PURE__ */ jsx("div", { className: "border-b px-6 py-4", children: /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
      /* @__PURE__ */ jsx(
        "button",
        {
          onClick: onBack,
          className: "rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800",
          children: /* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" })
        }
      ),
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ jsx(
          "img",
          {
            src: getAppIconUrl(sourceShortName, isDark ? "dark" : "light"),
            alt: sourceName,
            className: "h-6 w-6 rounded"
          }
        ),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsxs("h2", { className: "text-lg font-semibold text-gray-900 dark:text-white", children: [
            "Configure ",
            sourceName
          ] }),
          /* @__PURE__ */ jsx("p", { className: "text-sm text-gray-500 dark:text-gray-400", children: "Set up your connection settings" })
        ] })
      ] })
    ] }) }),
    /* @__PURE__ */ jsx("div", { className: "flex-1 overflow-auto px-6 py-6", children: /* @__PURE__ */ jsxs("div", { className: "space-y-6", children: [
      /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
        /* @__PURE__ */ jsx(Label, { className: "text-xs tracking-wider text-gray-500 uppercase dark:text-gray-400", children: "Connection Name" }),
        /* @__PURE__ */ jsx(
          Input,
          {
            value: connectionName,
            onChange: (e) => onConnectionNameChange(e.target.value),
            placeholder: "Enter connection name",
            className: "border-gray-200 bg-white placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:placeholder:text-gray-500"
          }
        ),
        connectionName && (connectionName.length < 4 || connectionName.length > 42) && /* @__PURE__ */ jsx("p", { className: "text-xs text-amber-500", children: "Name must be between 4 and 42 characters" })
      ] }),
      availableAuthMethods.length > 1 && /* @__PURE__ */ jsx(
        AuthMethodSelector,
        {
          availableAuthMethods,
          selectedAuthMode: authMode,
          onAuthModeChange
        }
      ),
      authMode === "direct_auth" && sourceDetails?.auth_fields?.fields && /* @__PURE__ */ jsx(
        DirectAuthFields,
        {
          fields: sourceDetails.auth_fields.fields,
          values: authFields,
          onChange: onAuthFieldChange
        }
      ),
      authMode === "oauth2" && /* @__PURE__ */ jsx(
        OAuthSettings,
        {
          sourceShortName,
          sourceName,
          requiresByoc: sourceDetails?.requires_byoc ?? false,
          useCustomOAuth,
          clientId,
          clientSecret,
          redirectUrl: getDefaultRedirectUrl(),
          onUseCustomOAuthChange,
          onClientIdChange,
          onClientSecretChange
        }
      ),
      sourceDetails?.config_fields?.fields && sourceDetails.config_fields.fields.length > 0 && /* @__PURE__ */ jsx(
        ConfigFields,
        {
          fields: sourceDetails.config_fields.fields,
          values: configFields,
          onChange: onConfigFieldChange
        }
      )
    ] }) }),
    /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between border-t border-gray-200 px-6 py-4 dark:border-gray-800", children: [
      /* @__PURE__ */ jsx(
        "button",
        {
          onClick: onCancel,
          className: "text-sm font-medium text-gray-600 transition-colors hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200",
          children: "Cancel"
        }
      ),
      /* @__PURE__ */ jsx(
        Button,
        {
          onClick: handleSubmit,
          disabled: !isFormValid || createMutation.isPending,
          className: cn(
            "min-w-[100px]",
            isFormValid && !createMutation.isPending ? "bg-blue-600 text-white hover:bg-blue-700" : ""
          ),
          children: createMutation.isPending ? /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 h-4 w-4 animate-spin" }),
            "Creating..."
          ] }) : "Create"
        }
      )
    ] })
  ] });
}
function AuthMethodSelector({
  availableAuthMethods,
  selectedAuthMode,
  onAuthModeChange
}) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
    /* @__PURE__ */ jsx(Label, { className: "text-xs tracking-wider text-gray-500 uppercase dark:text-gray-400", children: "Authentication Method" }),
    /* @__PURE__ */ jsxs("div", { className: "flex gap-2", children: [
      availableAuthMethods.includes("direct_auth") && /* @__PURE__ */ jsx(
        "button",
        {
          onClick: () => onAuthModeChange("direct_auth"),
          className: cn(
            "flex-1 rounded-lg border px-4 py-2 text-sm font-medium transition-colors",
            selectedAuthMode === "direct_auth" ? "border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400" : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-gray-600"
          ),
          children: "API Key / Credentials"
        }
      ),
      availableAuthMethods.includes("oauth2") && /* @__PURE__ */ jsx(
        "button",
        {
          onClick: () => onAuthModeChange("oauth2"),
          className: cn(
            "flex-1 rounded-lg border px-4 py-2 text-sm font-medium transition-colors",
            selectedAuthMode === "oauth2" ? "border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400" : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-gray-600"
          ),
          children: "OAuth"
        }
      )
    ] })
  ] });
}
const SOURCE_DESCRIPTIONS = {
  notion: "Connect to Notion to sync pages, databases, and workspace content.",
  postgresql: "Connect to PostgreSQL to sync tables, views, schemas, and records.",
  jira: "Connect to Jira to sync issues, projects, and team workflows.",
  hubspot: "Connect to HubSpot to sync contacts, companies, deals, and CRM data.",
  google_calendar: "Connect to Google Calendar to sync events and scheduling data.",
  google_drive: "Connect to Google Drive to sync files, folders, and documents.",
  gmail: "Connect to Gmail to sync email threads and attachments.",
  confluence: "Connect to Confluence to sync pages, spaces, and documentation.",
  todoist: "Connect to Todoist to sync projects, tasks, and productivity data.",
  github: "Connect to GitHub to sync repositories and code files.",
  stripe: "Connect to Stripe to sync customers, transactions, and billing data.",
  dropbox: "Connect to Dropbox to sync files and cloud storage data.",
  asana: "Connect to Asana to sync workspaces, projects, and tasks.",
  outlook_calendar: "Connect to Outlook Calendar to sync events and meetings.",
  outlook_mail: "Connect to Outlook Mail to sync emails and folders.",
  onedrive: "Connect to OneDrive to sync files and cloud storage.",
  monday: "Connect to Monday to sync boards and project management data.",
  bitbucket: "Connect to Bitbucket to sync repositories and pull requests.",
  linear: "Connect to Linear to sync issues and engineering workflows.",
  slack: "Connect to Slack to sync messages and channel data."
};
function SourceSelectView({
  onSelectSource,
  onCancel
}) {
  const isDark = useIsDark();
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const [searchQuery, setSearchQuery] = useState("");
  const { data: sources = [], isLoading } = useQuery({
    queryKey: ["sources", organization?.id],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSources(token, organization.id);
    },
    enabled: !!organization
  });
  const filteredSources = useMemo(() => {
    if (!searchQuery) return sources;
    const query = searchQuery.toLowerCase();
    return sources.filter(
      (source) => source.name.toLowerCase().includes(query) || source.short_name.toLowerCase().includes(query) || source.description?.toLowerCase().includes(query)
    );
  }, [sources, searchQuery]);
  const sortedSources = useMemo(() => {
    return [...filteredSources].sort((a, b) => a.name.localeCompare(b.name));
  }, [filteredSources]);
  const handleSelectSource = useCallback(
    (source) => {
      onSelectSource(source.short_name, source.name);
    },
    [onSelectSource]
  );
  const getSourceDescription = (source) => {
    return SOURCE_DESCRIPTIONS[source.short_name] || source.description || `Connect to ${source.name} to sync your data.`;
  };
  return /* @__PURE__ */ jsxs("div", { className: "flex h-full flex-col", children: [
    /* @__PURE__ */ jsxs("div", { className: "border-b px-6 py-4", children: [
      /* @__PURE__ */ jsxs("div", { className: "mb-4", children: [
        /* @__PURE__ */ jsx("h2", { className: "text-xl font-semibold text-gray-900 dark:text-white", children: "Select a source" }),
        /* @__PURE__ */ jsx("p", { className: "text-sm text-gray-500 dark:text-gray-400", children: "Choose a data source to connect to your collection" })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "relative", children: [
        /* @__PURE__ */ jsx(Search$1, { className: "absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-gray-400 dark:text-gray-500" }),
        /* @__PURE__ */ jsx(
          Input,
          {
            type: "text",
            placeholder: "Search sources...",
            value: searchQuery,
            onChange: (e) => setSearchQuery(e.target.value),
            className: "border-gray-200 bg-white pr-8 pl-9 placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:placeholder:text-gray-500",
            autoFocus: true
          }
        ),
        searchQuery && /* @__PURE__ */ jsx(
          "button",
          {
            onClick: () => setSearchQuery(""),
            className: "absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700",
            children: /* @__PURE__ */ jsx(X, { className: "h-3 w-3" })
          }
        )
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "mt-2 text-xs text-gray-400 dark:text-gray-500", children: [
        sortedSources.length,
        " ",
        sortedSources.length === 1 ? "source" : "sources",
        " available"
      ] })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "flex-1 overflow-auto p-6", children: isLoading ? /* @__PURE__ */ jsx("div", { className: "flex h-full items-center justify-center", children: /* @__PURE__ */ jsx(LoaderCircle, { className: "text-muted-foreground h-8 w-8 animate-spin" }) }) : sortedSources.length === 0 ? /* @__PURE__ */ jsxs("div", { className: "flex h-full flex-col items-center justify-center text-center", children: [
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: searchQuery ? "No sources found" : "No sources available" }),
      searchQuery && /* @__PURE__ */ jsx(
        "button",
        {
          onClick: () => setSearchQuery(""),
          className: "mt-2 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300",
          children: "Clear search"
        }
      )
    ] }) : /* @__PURE__ */ jsx("div", { className: "grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-5", children: sortedSources.map((source) => /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 300, children: /* @__PURE__ */ jsxs(Tooltip, { children: [
      /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsxs(
        "button",
        {
          onClick: () => handleSelectSource(source),
          className: "group flex flex-col items-center gap-2 rounded-lg border border-gray-200 bg-white p-4 transition-all hover:border-gray-300 hover:bg-gray-50 dark:border-gray-800 dark:bg-gray-900/50 dark:hover:border-gray-700 dark:hover:bg-gray-900",
          children: [
            /* @__PURE__ */ jsx("div", { className: "flex h-10 w-10 items-center justify-center overflow-hidden rounded-md", children: /* @__PURE__ */ jsx(
              "img",
              {
                src: getAppIconUrl(
                  source.short_name,
                  isDark ? "dark" : "light"
                ),
                alt: source.name,
                className: "h-full w-full object-contain",
                onError: (e) => {
                  e.target.style.display = "none";
                  const parent = e.target.parentElement;
                  if (parent) {
                    parent.innerHTML = `<span class="flex h-full w-full items-center justify-center rounded-md ${isDark ? "bg-gray-700 text-gray-300" : "bg-gray-100 text-gray-600"} text-lg font-semibold">${source.name.charAt(0).toUpperCase()}</span>`;
                  }
                }
              }
            ) }),
            /* @__PURE__ */ jsx("span", { className: "line-clamp-1 text-center text-xs font-medium text-gray-900 dark:text-white", children: source.name })
          ]
        }
      ) }),
      /* @__PURE__ */ jsx(
        TooltipContent,
        {
          side: "top",
          className: "max-w-xs border border-gray-200 bg-white p-4 text-gray-900 shadow-lg dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100",
          children: /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
            /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
              /* @__PURE__ */ jsx(
                "img",
                {
                  src: getAppIconUrl(
                    source.short_name,
                    isDark ? "dark" : "light"
                  ),
                  alt: source.name,
                  className: "h-5 w-5 rounded-sm"
                }
              ),
              /* @__PURE__ */ jsx("span", { className: "text-sm font-semibold", children: source.name })
            ] }),
            /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm leading-relaxed", children: getSourceDescription(source) }),
            source.labels && source.labels.length > 0 && /* @__PURE__ */ jsx("div", { className: "flex flex-wrap gap-1 pt-1", children: source.labels.map((label, idx) => /* @__PURE__ */ jsx(
              "span",
              {
                className: "rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300",
                children: label
              },
              idx
            )) })
          ] })
        }
      )
    ] }) }, source.short_name)) }) }),
    /* @__PURE__ */ jsx("div", { className: "border-t border-gray-200 px-6 py-4 dark:border-gray-800", children: /* @__PURE__ */ jsx(
      "button",
      {
        onClick: onCancel,
        className: "text-sm font-medium text-gray-600 transition-colors hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200",
        children: "Cancel"
      }
    ) })
  ] });
}
function SuccessView({
  collectionId,
  collectionName,
  sourceName,
  onClose
}) {
  const navigate = useNavigate();
  const { getOrgSlug, organization } = useOrg();
  const handleViewCollection = () => {
    if (organization) {
      const orgSlug = getOrgSlug(organization);
      navigate({ to: `/${orgSlug}/collections/${collectionId}` });
    }
    onClose();
  };
  return /* @__PURE__ */ jsx("div", { className: "flex h-full flex-col items-center justify-center px-6 py-12", children: /* @__PURE__ */ jsxs("div", { className: "max-w-sm space-y-6 text-center", children: [
    /* @__PURE__ */ jsx("div", { className: "mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30", children: /* @__PURE__ */ jsx(CircleCheckBig, { className: "h-10 w-10 text-green-600 dark:text-green-400" }) }),
    /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsx("h2", { className: "text-2xl font-semibold text-gray-900 dark:text-white", children: "Source connected!" }),
      /* @__PURE__ */ jsx("p", { className: "mt-2 text-gray-600 dark:text-gray-400", children: "Your data is now syncing" })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50", children: /* @__PURE__ */ jsxs("div", { className: "space-y-2 text-left", children: [
      /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between text-sm", children: [
        /* @__PURE__ */ jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Collection" }),
        /* @__PURE__ */ jsx("span", { className: "font-medium", children: collectionName })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between text-sm", children: [
        /* @__PURE__ */ jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Source" }),
        /* @__PURE__ */ jsx("span", { className: "font-medium", children: sourceName })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between text-sm", children: [
        /* @__PURE__ */ jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Status" }),
        /* @__PURE__ */ jsxs("span", { className: "flex items-center gap-1.5", children: [
          /* @__PURE__ */ jsx("span", { className: "h-2 w-2 animate-pulse rounded-full bg-green-500" }),
          /* @__PURE__ */ jsx("span", { className: "font-medium text-green-600 dark:text-green-400", children: "Syncing" })
        ] })
      ] })
    ] }) }),
    /* @__PURE__ */ jsxs("div", { className: "space-y-3", children: [
      /* @__PURE__ */ jsxs(
        Button,
        {
          onClick: handleViewCollection,
          className: "w-full bg-blue-600 text-white hover:bg-blue-700",
          children: [
            "View Collection",
            /* @__PURE__ */ jsx(ArrowRight, { className: "ml-2 h-4 w-4" })
          ]
        }
      ),
      /* @__PURE__ */ jsx(
        "button",
        {
          onClick: onClose,
          className: "w-full rounded-lg px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200",
          children: "Done"
        }
      )
    ] })
  ] }) });
}
function AddSourceDialog({ open, onOpenChange }) {
  const {
    currentStep,
    collectionId,
    collectionName,
    selectedSourceShortName,
    selectedSourceName,
    connectionName,
    authMode,
    authFields,
    configFields,
    useCustomOAuth,
    clientId,
    clientSecret,
    customRedirectUrl,
    selectSource,
    setStep,
    goBack,
    setConnectionName,
    setAuthMode,
    setAuthField,
    setConfigField,
    setUseCustomOAuth,
    setClientId,
    setClientSecret,
    setCustomRedirectUrl,
    completeWithOAuth,
    completeWithoutOAuth,
    reset,
    close
  } = useAddSourceStore();
  const handleOpenChange = useCallback(
    (newOpen) => {
      if (!newOpen) {
        close();
        setTimeout(() => {
          reset();
        }, 300);
      }
      onOpenChange(newOpen);
    },
    [close, reset, onOpenChange]
  );
  const handleSelectSource = useCallback(
    (shortName, displayName) => {
      selectSource(shortName, displayName);
    },
    [selectSource]
  );
  const handleConnectionSuccess = useCallback(
    (connectionId, oauthUrl) => {
      if (oauthUrl) {
        completeWithOAuth(connectionId, oauthUrl);
      } else {
        completeWithoutOAuth(connectionId);
      }
    },
    [completeWithOAuth, completeWithoutOAuth]
  );
  const handleCancel = useCallback(() => {
    handleOpenChange(false);
  }, [handleOpenChange]);
  const handleBack = useCallback(() => {
    goBack();
  }, [goBack]);
  const getDialogSize = () => {
    switch (currentStep) {
      case "source-select":
        return "max-w-4xl";
      case "source-config":
      case "oauth-pending":
        return "max-w-lg";
      case "success":
        return "max-w-md";
      default:
        return "max-w-2xl";
    }
  };
  const renderContent = () => {
    if (!collectionId || !collectionName) {
      return null;
    }
    switch (currentStep) {
      case "source-select":
        return /* @__PURE__ */ jsx(
          SourceSelectView,
          {
            onSelectSource: handleSelectSource,
            onCancel: handleCancel
          }
        );
      case "source-config":
      case "oauth-pending":
        if (!selectedSourceShortName || !selectedSourceName) {
          setStep("source-select");
          return null;
        }
        return /* @__PURE__ */ jsx(
          SourceConfigView,
          {
            collectionId,
            collectionName,
            sourceShortName: selectedSourceShortName,
            sourceName: selectedSourceName,
            connectionName,
            authMode,
            authFields,
            configFields,
            useCustomOAuth,
            clientId,
            clientSecret,
            customRedirectUrl,
            onBack: handleBack,
            onConnectionNameChange: setConnectionName,
            onAuthModeChange: setAuthMode,
            onAuthFieldChange: setAuthField,
            onConfigFieldChange: setConfigField,
            onUseCustomOAuthChange: setUseCustomOAuth,
            onClientIdChange: setClientId,
            onClientSecretChange: setClientSecret,
            onCustomRedirectUrlChange: setCustomRedirectUrl,
            onSuccess: handleConnectionSuccess,
            onCancel: handleCancel
          }
        );
      case "success":
        return /* @__PURE__ */ jsx(
          SuccessView,
          {
            collectionId,
            collectionName,
            sourceName: selectedSourceName || "Source",
            onClose: handleCancel
          }
        );
      default:
        return null;
    }
  };
  return /* @__PURE__ */ jsx(Dialog, { open, onOpenChange: handleOpenChange, children: /* @__PURE__ */ jsxs(
    DialogContent,
    {
      className: `${getDialogSize()} h-[600px] overflow-hidden p-0`,
      onPointerDownOutside: (e) => {
        if (currentStep === "oauth-pending") {
          e.preventDefault();
        }
      },
      onEscapeKeyDown: (e) => {
        if (currentStep === "oauth-pending") {
          e.preventDefault();
        }
      },
      children: [
        /* @__PURE__ */ jsxs(VisuallyHidden, { children: [
          /* @__PURE__ */ jsx(DialogTitle, { children: "Add Source to Collection" }),
          /* @__PURE__ */ jsx(DialogDescription, { children: "Select and configure a data source to connect to your collection" })
        ] }),
        renderContent()
      ]
    }
  ) });
}
const STATUS_CONFIG = {
  ACTIVE: {
    label: "Active",
    className: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
  },
  NEEDS_SOURCE: {
    label: "Needs Source",
    className: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
  },
  ERROR: {
    label: "Error",
    className: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
  }
};
function StatusBadge({ status }) {
  const config = STATUS_CONFIG[status] || {
    label: status,
    className: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400"
  };
  return /* @__PURE__ */ jsx(
    "span",
    {
      className: cn(
        "inline-flex items-center rounded-md px-2 py-1 text-xs font-medium",
        config.className
      ),
      children: config.label
    }
  );
}
function CollectionHeader({
  collection,
  sourceConnections,
  onReload,
  onDelete,
  onSaveName
}) {
  const [isEditingName, setIsEditingName] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const nameInputRef = useRef(null);
  const startEditingName = useCallback(() => {
    setIsEditingName(true);
    setTimeout(() => {
      if (nameInputRef.current && collection) {
        nameInputRef.current.innerText = collection.name;
        const range = document.createRange();
        const selection = window.getSelection();
        const textNode = nameInputRef.current.firstChild || nameInputRef.current;
        const textLength = nameInputRef.current.innerText.length;
        range.setStart(textNode, textLength);
        range.setEnd(textNode, textLength);
        if (selection) {
          selection.removeAllRanges();
          selection.addRange(range);
        }
        nameInputRef.current.focus();
      }
    }, 0);
  }, [collection]);
  const handleSaveNameChange = useCallback(async () => {
    const newName = nameInputRef.current?.innerText.trim() || "";
    if (!newName || newName === collection?.name) {
      setIsEditingName(false);
      return;
    }
    try {
      await onSaveName?.(newName);
      setIsEditingName(false);
      toast.success("Collection name updated");
    } catch {
      toast.error("Failed to update collection name");
      setIsEditingName(false);
    }
  }, [collection, onSaveName]);
  const handleCopyId = useCallback(() => {
    if (collection?.readable_id) {
      navigator.clipboard.writeText(collection.readable_id);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 1500);
      toast.success("ID copied to clipboard");
    }
  }, [collection]);
  return /* @__PURE__ */ jsxs("div", { className: "flex w-full items-center justify-between py-4", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
      /* @__PURE__ */ jsxs(
        "div",
        {
          className: "flex items-center justify-start",
          style: { minWidth: "3.5rem" },
          children: [
            sourceConnections.slice(0, 3).map((connection, index) => /* @__PURE__ */ jsx(
              "div",
              {
                className: "bg-background flex size-12 items-center justify-center overflow-hidden rounded-md border p-1",
                style: {
                  marginLeft: index > 0 ? `-${Math.min(index * 8, 24)}px` : "0px",
                  zIndex: 3 - index
                },
                children: /* @__PURE__ */ jsx(
                  "img",
                  {
                    src: getAppIconUrl(connection.short_name),
                    alt: connection.name,
                    className: "size-auto max-h-full max-w-full object-contain"
                  }
                )
              },
              connection.id
            )),
            sourceConnections.length > 3 && /* @__PURE__ */ jsxs("div", { className: "text-muted-foreground ml-2 text-sm font-medium", children: [
              "+",
              sourceConnections.length - 3
            ] })
          ]
        }
      ),
      /* @__PURE__ */ jsxs("div", { className: "flex flex-col justify-center", children: [
        isEditingName ? /* @__PURE__ */ jsx("div", { className: "flex items-center gap-2", children: /* @__PURE__ */ jsx(
          "div",
          {
            ref: nameInputRef,
            contentEditable: true,
            className: "text-foreground border-border/40 rounded border p-1 pr-3 pl-0 text-3xl font-bold tracking-tight transition-all duration-150 outline-none",
            onKeyDown: (e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSaveNameChange();
              }
              if (e.key === "Escape") {
                e.preventDefault();
                setIsEditingName(false);
              }
            },
            onBlur: handleSaveNameChange
          }
        ) }) : /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
          /* @__PURE__ */ jsx("h1", { className: "text-foreground py-1 pl-0 text-2xl font-bold tracking-tight", children: collection.name }),
          /* @__PURE__ */ jsx(
            Button,
            {
              variant: "ghost",
              size: "icon",
              className: "text-muted-foreground hover:text-foreground size-6",
              onClick: startEditingName,
              children: /* @__PURE__ */ jsx(Pencil, { className: "size-3" })
            }
          ),
          collection.status && /* @__PURE__ */ jsx(StatusBadge, { status: collection.status })
        ] }),
        /* @__PURE__ */ jsxs("p", { className: "text-muted-foreground group relative flex items-center text-sm", children: [
          collection.readable_id,
          /* @__PURE__ */ jsx(
            "button",
            {
              className: "ml-1.5 opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100 focus:outline-none",
              onClick: handleCopyId,
              title: "Copy ID",
              children: isCopied ? /* @__PURE__ */ jsx(Check, { className: "text-muted-foreground size-3.5 transition-all" }) : /* @__PURE__ */ jsx(Copy, { className: "text-muted-foreground size-3.5 transition-all" })
            }
          )
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1.5", children: [
      /* @__PURE__ */ jsx(TooltipProvider, { children: /* @__PURE__ */ jsxs(Tooltip, { children: [
        /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(
          Button,
          {
            variant: "outline",
            size: "icon",
            className: "size-8",
            onClick: onReload,
            children: /* @__PURE__ */ jsx(RotateCw, { className: "size-3" })
          }
        ) }),
        /* @__PURE__ */ jsx(TooltipContent, { children: /* @__PURE__ */ jsx("p", { children: "Reload page" }) })
      ] }) }),
      /* @__PURE__ */ jsx(TooltipProvider, { children: /* @__PURE__ */ jsxs(Tooltip, { children: [
        /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(
          Button,
          {
            variant: "outline",
            size: "icon",
            className: "size-8",
            onClick: onDelete,
            children: /* @__PURE__ */ jsx(Trash, { className: "size-3" })
          }
        ) }),
        /* @__PURE__ */ jsx(TooltipContent, { children: /* @__PURE__ */ jsx("p", { children: "Delete collection" }) })
      ] }) })
    ] })
  ] });
}
function DeleteCollectionDialog({
  open,
  onOpenChange,
  onConfirm,
  collectionReadableId,
  isDeleting
}) {
  const [confirmText, setConfirmText] = useState("");
  const isConfirmValid = confirmText === collectionReadableId;
  useEffect(() => {
    if (!open) {
      setConfirmText("");
    }
  }, [open]);
  return /* @__PURE__ */ jsx(AlertDialog, { open, onOpenChange, children: /* @__PURE__ */ jsxs(AlertDialogContent, { className: "max-w-md", children: [
    /* @__PURE__ */ jsxs(AlertDialogHeader, { className: "space-y-4", children: [
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
        /* @__PURE__ */ jsx("div", { className: "bg-destructive/10 flex size-10 flex-shrink-0 items-center justify-center rounded-full", children: /* @__PURE__ */ jsx(TriangleAlert, { className: "text-destructive size-5" }) }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx(AlertDialogTitle, { className: "text-foreground text-lg font-semibold", children: "Delete Collection" }),
          /* @__PURE__ */ jsx("p", { className: "text-muted-foreground mt-1 text-sm", children: "This action cannot be undone" })
        ] })
      ] }),
      /* @__PURE__ */ jsxs(AlertDialogDescription, { className: "space-y-4", children: [
        /* @__PURE__ */ jsxs("div", { className: "bg-destructive/5 border-destructive/20 rounded-lg border p-4", children: [
          /* @__PURE__ */ jsx("p", { className: "text-foreground mb-3 font-medium", children: "This will permanently delete:" }),
          /* @__PURE__ */ jsxs("ul", { className: "text-muted-foreground space-y-2 text-sm", children: [
            /* @__PURE__ */ jsxs("li", { className: "flex items-start gap-2", children: [
              /* @__PURE__ */ jsx("div", { className: "bg-destructive/60 mt-2 size-1.5 flex-shrink-0 rounded-full" }),
              /* @__PURE__ */ jsx("span", { children: "The collection and all its source connections" })
            ] }),
            /* @__PURE__ */ jsxs("li", { className: "flex items-start gap-2", children: [
              /* @__PURE__ */ jsx("div", { className: "bg-destructive/60 mt-2 size-1.5 flex-shrink-0 rounded-full" }),
              /* @__PURE__ */ jsx("span", { children: "All synced data from the knowledge base" })
            ] }),
            /* @__PURE__ */ jsxs("li", { className: "flex items-start gap-2", children: [
              /* @__PURE__ */ jsx("div", { className: "bg-destructive/60 mt-2 size-1.5 flex-shrink-0 rounded-full" }),
              /* @__PURE__ */ jsx("span", { children: "All sync history and configuration" })
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "space-y-3", children: [
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsxs(
              "label",
              {
                htmlFor: "confirm-delete",
                className: "text-foreground mb-2 block text-sm font-medium",
                children: [
                  "Type",
                  " ",
                  /* @__PURE__ */ jsx("span", { className: "bg-destructive/10 text-destructive rounded px-1.5 py-0.5 font-mono font-semibold", children: collectionReadableId }),
                  " ",
                  "to confirm deletion"
                ]
              }
            ),
            /* @__PURE__ */ jsx(
              Input,
              {
                id: "confirm-delete",
                value: confirmText,
                onChange: (e) => setConfirmText(e.target.value),
                className: cn(
                  "w-full transition-colors",
                  isConfirmValid && confirmText.length > 0 ? "border-green-500 focus:border-green-500 focus:ring-green-500/20" : confirmText.length > 0 ? "border-destructive focus:border-destructive focus:ring-destructive/20" : ""
                ),
                placeholder: collectionReadableId
              }
            )
          ] }),
          confirmText.length > 0 && /* @__PURE__ */ jsx("div", { className: "flex items-center gap-2 text-sm", children: isConfirmValid ? /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx(Check, { className: "size-4 text-green-500" }),
            /* @__PURE__ */ jsx("span", { className: "text-green-600 dark:text-green-400", children: "Confirmation matches" })
          ] }) : /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx(CircleAlert, { className: "text-destructive size-4" }),
            /* @__PURE__ */ jsx("span", { className: "text-destructive", children: "Confirmation does not match" })
          ] }) })
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsxs(AlertDialogFooter, { className: "gap-3", children: [
      /* @__PURE__ */ jsx(AlertDialogCancel, { className: "flex-1", children: "Cancel" }),
      /* @__PURE__ */ jsxs(
        AlertDialogAction,
        {
          onClick: onConfirm,
          disabled: !isConfirmValid || isDeleting,
          className: cn(
            "bg-destructive text-destructive-foreground hover:bg-destructive/90 flex-1",
            "disabled:cursor-not-allowed disabled:opacity-50",
            "transition-all duration-200"
          ),
          children: [
            isDeleting ? /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 size-4 animate-spin" }) : /* @__PURE__ */ jsx(Trash, { className: "mr-2 size-4" }),
            "Delete Collection"
          ]
        }
      )
    ] })
  ] }) });
}
function EntityStateList({
  entityStates = [],
  isRunning,
  isPending,
  onStartSync,
  className
}) {
  const formatEntityType = (type) => {
    return type.replace(/Entity$/, "").replace(/([A-Z])/g, " $1").trim();
  };
  const getStatusIndicator = (status) => {
    switch (status) {
      case "syncing":
        return /* @__PURE__ */ jsx("span", { className: "inline-flex size-2 animate-pulse rounded-full bg-blue-500" });
      case "synced":
        return /* @__PURE__ */ jsx("span", { className: "inline-flex size-2 rounded-full bg-green-500" });
      case "failed":
        return /* @__PURE__ */ jsx("span", { className: "inline-flex size-2 rounded-full bg-red-500" });
      default:
        return /* @__PURE__ */ jsx("span", { className: "inline-flex size-2 rounded-full bg-gray-400" });
    }
  };
  if (entityStates.length === 0) {
    return /* @__PURE__ */ jsx(
      EmptyState,
      {
        icon: /* @__PURE__ */ jsx(FileText, {}),
        title: "No entities synced",
        description: "Start a sync to begin indexing your data",
        className: cn("rounded-lg border-2 border-dashed py-8", className),
        children: onStartSync && /* @__PURE__ */ jsx(
          Button,
          {
            variant: "outline",
            size: "sm",
            onClick: onStartSync,
            disabled: isRunning || isPending,
            children: isRunning || isPending ? /* @__PURE__ */ jsxs(Fragment, { children: [
              /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 size-4 animate-spin" }),
              "Syncing..."
            ] }) : /* @__PURE__ */ jsxs(Fragment, { children: [
              /* @__PURE__ */ jsx(Play, { className: "mr-2 size-4" }),
              "Start Sync"
            ] })
          }
        )
      }
    );
  }
  const totalEntities = entityStates.reduce(
    (sum, state) => sum + state.total_count,
    0
  );
  return /* @__PURE__ */ jsxs("div", { className: cn("space-y-3", className), children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between", children: [
      /* @__PURE__ */ jsxs("div", { className: "text-sm", children: [
        /* @__PURE__ */ jsx("span", { className: "text-muted-foreground", children: "Total entities: " }),
        /* @__PURE__ */ jsx("span", { className: "font-semibold", children: totalEntities.toLocaleString() })
      ] }),
      (isRunning || isPending) && /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400", children: [
        /* @__PURE__ */ jsx(LoaderCircle, { className: "size-4 animate-spin" }),
        /* @__PURE__ */ jsx("span", { children: "Syncing..." })
      ] })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "grid gap-2 sm:grid-cols-2 lg:grid-cols-3", children: entityStates.map((state) => /* @__PURE__ */ jsxs(
      "div",
      {
        className: "bg-card flex items-center justify-between rounded-lg border p-3",
        children: [
          /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
            getStatusIndicator(state.sync_status),
            /* @__PURE__ */ jsx("span", { className: "text-sm font-medium", children: formatEntityType(state.entity_type) })
          ] }),
          /* @__PURE__ */ jsx("span", { className: "text-muted-foreground text-sm", children: state.total_count.toLocaleString() })
        ]
      },
      state.entity_type
    )) })
  ] });
}
function DeleteSourceDialog({
  open,
  onOpenChange,
  onConfirm,
  sourceName,
  isDeleting,
  hasData = true
}) {
  return /* @__PURE__ */ jsx(AlertDialog, { open, onOpenChange, children: /* @__PURE__ */ jsxs(AlertDialogContent, { children: [
    /* @__PURE__ */ jsxs(AlertDialogHeader, { children: [
      /* @__PURE__ */ jsx(AlertDialogTitle, { children: "Delete Source Connection" }),
      /* @__PURE__ */ jsxs(AlertDialogDescription, { children: [
        'Are you sure you want to delete "',
        sourceName,
        '"?',
        hasData ? " This will permanently remove all synced data from this source." : " This will permanently remove this connection."
      ] })
    ] }),
    /* @__PURE__ */ jsxs(AlertDialogFooter, { children: [
      /* @__PURE__ */ jsx(AlertDialogCancel, { children: "Cancel" }),
      /* @__PURE__ */ jsxs(
        AlertDialogAction,
        {
          onClick: onConfirm,
          disabled: isDeleting,
          className: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
          children: [
            isDeleting ? /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 size-4 animate-spin" }) : /* @__PURE__ */ jsx(Trash2, { className: "mr-2 size-4" }),
            "Delete"
          ]
        }
      )
    ] })
  ] }) });
}
function FederatedSearchInfo() {
  return /* @__PURE__ */ jsx("div", { className: "rounded-lg border border-blue-800/30 bg-blue-900/10 p-4", children: /* @__PURE__ */ jsxs("div", { className: "flex items-start gap-3", children: [
    /* @__PURE__ */ jsx(Send, { className: "mt-0.5 size-5 text-blue-400" }),
    /* @__PURE__ */ jsx("div", { className: "flex-1 space-y-2", children: /* @__PURE__ */ jsx("p", { className: "text-sm text-blue-200/80", children: "This source searches the data at query time instead of syncing and indexing it beforehand." }) })
  ] }) });
}
function SyncErrorCard({ error, className }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "border-destructive/50 bg-destructive/10 rounded-lg border p-4",
        className
      ),
      children: /* @__PURE__ */ jsxs("div", { className: "flex items-start gap-3", children: [
        /* @__PURE__ */ jsx(CircleAlert, { className: "text-destructive mt-0.5 size-5 flex-shrink-0" }),
        /* @__PURE__ */ jsxs("div", { className: "flex-1 space-y-1", children: [
          /* @__PURE__ */ jsx("p", { className: "text-destructive text-sm font-medium", children: "Sync Failed" }),
          /* @__PURE__ */ jsx("p", { className: "text-destructive/80 text-sm", children: error })
        ] })
      ] })
    }
  );
}
function SyncStatusDashboard({
  isFederatedSource,
  syncState,
  isSyncing,
  entityCount,
  statusDisplay,
  scheduleCron,
  scheduleNextRun,
  lastSyncTime,
  onSync,
  onCancelSync,
  onDelete,
  isSyncPending,
  isCancelPending
}) {
  return /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex flex-wrap items-center gap-2", children: [
      !isFederatedSource && /* @__PURE__ */ jsxs("div", { className: "bg-card flex h-8 min-w-[90px] items-center gap-2 rounded-md border px-3 py-1.5 shadow-sm", children: [
        /* @__PURE__ */ jsx("span", { className: "text-muted-foreground/60 text-[10px] font-medium tracking-wider uppercase", children: "ENTITIES" }),
        /* @__PURE__ */ jsx("span", { className: "text-foreground text-xs font-semibold", children: entityCount.toLocaleString() })
      ] }),
      /* @__PURE__ */ jsxs(
        "div",
        {
          className: cn(
            "flex h-8 min-w-[90px] items-center gap-2 rounded-md border px-3 py-1.5 shadow-sm",
            isSyncing ? "border-blue-700/50 bg-blue-900/30" : "border-border bg-card"
          ),
          children: [
            /* @__PURE__ */ jsx("span", { className: "text-muted-foreground/60 text-[10px] font-medium tracking-wider uppercase", children: "STATUS" }),
            /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1", children: [
              statusDisplay.icon === "loader" ? /* @__PURE__ */ jsx(LoaderCircle, { className: "size-3 animate-spin text-blue-500" }) : /* @__PURE__ */ jsx(
                "span",
                {
                  className: cn(
                    "inline-flex size-2 rounded-full",
                    statusDisplay.color
                  )
                }
              ),
              /* @__PURE__ */ jsx(
                "span",
                {
                  className: cn(
                    "text-xs font-medium capitalize",
                    isSyncing ? "text-blue-400" : "text-foreground"
                  ),
                  children: statusDisplay.text
                }
              )
            ] })
          ]
        }
      ),
      !isFederatedSource && scheduleCron && /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 100, children: /* @__PURE__ */ jsxs(Tooltip, { children: [
        /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsxs("div", { className: "bg-card flex h-8 min-w-[100px] cursor-help items-center gap-2 rounded-md border px-3 py-1.5 shadow-sm", children: [
          /* @__PURE__ */ jsx("span", { className: "text-muted-foreground/60 text-[10px] font-medium tracking-wider uppercase", children: "SCHEDULE" }),
          /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1", children: [
            /* @__PURE__ */ jsx(Clock, { className: "text-muted-foreground size-3" }),
            /* @__PURE__ */ jsx("span", { className: "text-foreground text-xs font-medium", children: scheduleCron })
          ] })
        ] }) }),
        /* @__PURE__ */ jsx(TooltipContent, { children: /* @__PURE__ */ jsxs("p", { className: "text-xs", children: [
          "Next run: ",
          scheduleNextRun || "Not scheduled"
        ] }) })
      ] }) }),
      !isFederatedSource && !isSyncing && lastSyncTime && /* @__PURE__ */ jsxs("div", { className: "bg-card flex h-8 min-w-[100px] items-center gap-2 rounded-md border px-3 py-1.5 shadow-sm", children: [
        /* @__PURE__ */ jsx("span", { className: "text-muted-foreground/60 text-[10px] font-medium tracking-wider uppercase", children: "LAST SYNC" }),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1", children: [
          /* @__PURE__ */ jsx(History, { className: "text-muted-foreground size-3" }),
          /* @__PURE__ */ jsx("span", { className: "text-foreground text-xs font-medium", children: lastSyncTime })
        ] })
      ] }),
      isFederatedSource && /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 100, children: /* @__PURE__ */ jsxs(Tooltip, { children: [
        /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsxs("div", { className: "flex h-8 cursor-help items-center gap-2 rounded-md border border-blue-800/30 bg-blue-900/20 px-3 py-1.5 shadow-sm", children: [
          /* @__PURE__ */ jsx("span", { className: "text-muted-foreground/60 text-[10px] font-medium tracking-wider uppercase", children: "MODE" }),
          /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1", children: [
            /* @__PURE__ */ jsx(Send, { className: "size-3 text-blue-500" }),
            /* @__PURE__ */ jsx("span", { className: "text-xs font-medium text-blue-400", children: "Federated search" })
          ] })
        ] }) }),
        /* @__PURE__ */ jsx(TooltipContent, { children: /* @__PURE__ */ jsx("p", { className: "max-w-[240px] text-xs", children: "Data is queried in real-time when you search instead of being synced and indexed." }) })
      ] }) })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1.5", children: [
      !isFederatedSource && /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 100, children: /* @__PURE__ */ jsxs(Tooltip, { children: [
        /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(
          Button,
          {
            variant: "outline",
            size: "icon",
            className: "size-8",
            onClick: () => {
              if (syncState === "IDLE") {
                onSync();
              } else if (syncState === "SYNCING") {
                onCancelSync();
              }
            },
            disabled: syncState === "CANCELLING" || isSyncPending || isCancelPending,
            children: syncState === "CANCELLING" || isCancelPending ? /* @__PURE__ */ jsx(LoaderCircle, { className: "size-3 animate-spin text-orange-500" }) : syncState === "SYNCING" ? /* @__PURE__ */ jsx(Square, { className: "size-3 text-red-500" }) : isSyncPending ? /* @__PURE__ */ jsx(LoaderCircle, { className: "size-3 animate-spin" }) : /* @__PURE__ */ jsx(RefreshCw, { className: "size-3" })
          }
        ) }),
        /* @__PURE__ */ jsx(TooltipContent, { children: syncState === "CANCELLING" ? "Cancelling sync..." : syncState === "SYNCING" ? "Cancel sync" : "Refresh data" })
      ] }) }),
      /* @__PURE__ */ jsxs(DropdownMenu, { children: [
        /* @__PURE__ */ jsx(DropdownMenuTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "icon", className: "size-8", children: /* @__PURE__ */ jsx(Settings, { className: "size-3" }) }) }),
        /* @__PURE__ */ jsx(DropdownMenuContent, { align: "end", children: /* @__PURE__ */ jsxs(
          DropdownMenuItem,
          {
            onClick: onDelete,
            className: "text-destructive focus:text-destructive",
            children: [
              /* @__PURE__ */ jsx(Trash2, { className: "mr-2 size-4" }),
              "Delete Connection"
            ]
          }
        ) })
      ] })
    ] })
  ] });
}
function formatTimeAgo(dateStr) {
  if (!dateStr) return null;
  const hasTimezone = dateStr.endsWith("Z") || dateStr.match(/[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:?\d{2}$/);
  const utcDateStr = hasTimezone ? dateStr : `${dateStr}Z`;
  const date = new Date(utcDateStr);
  const now = /* @__PURE__ */ new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1e3 * 60));
  const diffHrs = Math.floor(diffMs / (1e3 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1e3 * 60 * 60 * 24));
  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHrs > 0) return `${diffHrs}h ago`;
  if (diffMins > 0) return `${diffMins}m ago`;
  return "Just now";
}
function getSyncStatusDisplay(isNotAuthorized, isFederatedSource, syncState, jobStatus) {
  if (isNotAuthorized) {
    return { text: "Not Authenticated", color: "bg-cyan-500", icon: null };
  }
  if (isFederatedSource) {
    return { text: "Ready", color: "bg-green-500", icon: null };
  }
  if (syncState === "CANCELLING") {
    return {
      text: "Cancelling",
      color: "bg-orange-500 animate-pulse",
      icon: "loader"
    };
  }
  if (jobStatus === "failed") {
    return { text: "Failed", color: "bg-red-500", icon: null };
  }
  if (jobStatus === "completed") {
    return { text: "Completed", color: "bg-green-500", icon: null };
  }
  if (jobStatus === "cancelled") {
    return { text: "Cancelled", color: "bg-gray-500", icon: null };
  }
  if (jobStatus === "running" || jobStatus === "in_progress") {
    return {
      text: "Syncing",
      color: "bg-blue-500 animate-pulse",
      icon: "loader"
    };
  }
  if (jobStatus === "pending" || jobStatus === "created") {
    return {
      text: "Pending",
      color: "bg-yellow-500 animate-pulse",
      icon: "loader"
    };
  }
  return { text: "Ready", color: "bg-gray-400", icon: null };
}
function SourceConnectionStateView({
  sourceConnection: initialSourceConnection,
  onConnectionDeleted,
  onConnectionUpdated
}) {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const queryClient = useQueryClient();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isRefreshingAuth, setIsRefreshingAuth] = useState(false);
  if (!organization) {
    throw new Error("Organization context is required");
  }
  const orgId = organization.id;
  const { data: detailedConnection } = useQuery({
    queryKey: queryKeys.sourceConnections.detail(
      orgId,
      initialSourceConnection.id
    ),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSourceConnection(token, orgId, initialSourceConnection.id);
    },
    initialData: initialSourceConnection,
    refetchOnMount: true,
    staleTime: 0
  });
  const sourceConnection = detailedConnection || initialSourceConnection;
  const isFederatedSource = sourceConnection.federated_search === true;
  const isNotAuthorized = sourceConnection.status === "pending_auth" || !sourceConnection.auth?.authenticated;
  const currentSyncJob = sourceConnection.last_sync_job;
  const jobStatus = currentSyncJob?.status;
  const syncState = useMemo(() => {
    if (jobStatus === "cancelling") return "CANCELLING";
    if (["running", "in_progress", "pending", "created"].includes(jobStatus || "")) {
      return "SYNCING";
    }
    return "IDLE";
  }, [jobStatus]);
  const isRunning = jobStatus === "running" || jobStatus === "in_progress";
  const isPending = jobStatus === "pending" || jobStatus === "created";
  const isSyncing = syncState !== "IDLE";
  const runSyncMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return runSourceConnectionSync(token, orgId, sourceConnection.id);
    },
    onSuccess: () => {
      toast.success("Sync started");
      onConnectionUpdated?.();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to start sync"
      );
    }
  });
  const cancelSyncMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      if (currentSyncJob?.id) {
        return cancelSourceConnectionSync(
          token,
          orgId,
          sourceConnection.id,
          currentSyncJob.id
        );
      }
    },
    onSuccess: () => {
      toast.success("Cancellation requested");
      onConnectionUpdated?.();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to cancel sync"
      );
    }
  });
  const deleteMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return deleteSourceConnection(token, orgId, sourceConnection.id);
    },
    onSuccess: () => {
      toast.success("Source connection deleted");
      setShowDeleteDialog(false);
      queryClient.invalidateQueries({
        queryKey: queryKeys.sourceConnections.all(
          orgId,
          sourceConnection.readable_collection_id
        )
      });
      onConnectionDeleted?.();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to delete source connection"
      );
    }
  });
  const handleRefreshAuthUrl = useCallback(async () => {
    setIsRefreshingAuth(true);
    try {
      const token = await getAccessTokenSilently();
      await fetchSourceConnection(
        token,
        orgId,
        initialSourceConnection.id,
        true
      );
      toast.success("Authentication URL refreshed");
      queryClient.invalidateQueries({
        queryKey: queryKeys.sourceConnections.detail(
          orgId,
          initialSourceConnection.id
        )
      });
      onConnectionUpdated?.();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to refresh authentication URL"
      );
    } finally {
      setIsRefreshingAuth(false);
    }
  }, [
    getAccessTokenSilently,
    orgId,
    initialSourceConnection.id,
    queryClient,
    onConnectionUpdated
  ]);
  const syncStatus = getSyncStatusDisplay(
    isNotAuthorized,
    isFederatedSource,
    syncState,
    jobStatus
  );
  const lastRanDisplay = formatTimeAgo(
    sourceConnection.last_sync_job?.started_at
  );
  const entityStates = sourceConnection.entities ? Object.entries(sourceConnection.entities.by_type).map(
    ([type, stats]) => ({
      entity_type: type,
      total_count: stats.count,
      last_updated_at: stats.last_updated,
      sync_status: stats.sync_status
    })
  ) : [];
  if (isNotAuthorized) {
    return /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx(
        SourceAuthenticationView,
        {
          sourceName: sourceConnection.name,
          sourceShortName: sourceConnection.short_name,
          authenticationUrl: sourceConnection.auth?.auth_url,
          onRefreshUrl: handleRefreshAuthUrl,
          isRefreshing: isRefreshingAuth,
          onDelete: () => setShowDeleteDialog(true)
        }
      ),
      /* @__PURE__ */ jsx(
        DeleteSourceDialog,
        {
          open: showDeleteDialog,
          onOpenChange: setShowDeleteDialog,
          onConfirm: () => deleteMutation.mutate(),
          sourceName: sourceConnection.name,
          isDeleting: deleteMutation.isPending,
          hasData: false
        }
      )
    ] });
  }
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx(
      SyncStatusDashboard,
      {
        isFederatedSource,
        syncState,
        isSyncing,
        entityCount: sourceConnection.entities?.total_entities || 0,
        statusDisplay: syncStatus,
        scheduleCron: sourceConnection.schedule?.cron,
        scheduleNextRun: sourceConnection.schedule?.next_run,
        lastSyncTime: lastRanDisplay,
        onSync: () => runSyncMutation.mutate(),
        onCancelSync: () => cancelSyncMutation.mutate(),
        onDelete: () => setShowDeleteDialog(true),
        isSyncPending: runSyncMutation.isPending,
        isCancelPending: cancelSyncMutation.isPending
      }
    ),
    !isFederatedSource && currentSyncJob?.status === "failed" && /* @__PURE__ */ jsx(
      SyncErrorCard,
      {
        error: currentSyncJob.error || "The last sync failed. Check the logs for more details."
      }
    ),
    isFederatedSource && /* @__PURE__ */ jsx(FederatedSearchInfo, {}),
    !isFederatedSource && /* @__PURE__ */ jsx(
      EntityStateList,
      {
        entityStates,
        isRunning,
        isPending,
        onStartSync: () => runSyncMutation.mutate()
      }
    ),
    /* @__PURE__ */ jsx(
      DeleteSourceDialog,
      {
        open: showDeleteDialog,
        onOpenChange: setShowDeleteDialog,
        onConfirm: () => deleteMutation.mutate(),
        sourceName: sourceConnection.name,
        isDeleting: deleteMutation.isPending,
        hasData: true
      }
    )
  ] });
}
function getConnectionStatusIndicator(connection) {
  const isFederated = connection.federated_search === true;
  let colorClass = "bg-gray-400";
  let status = "unknown";
  let isAnimated = false;
  if (isFederated) {
    switch (connection.status) {
      case "pending_auth":
        colorClass = "bg-cyan-500";
        status = "Authentication required";
        break;
      case "error":
        colorClass = "bg-red-500";
        status = "Connection error";
        break;
      case "inactive":
        colorClass = "bg-gray-400";
        status = "Inactive";
        break;
      case "active":
      default:
        colorClass = "bg-green-500";
        status = "Ready for real-time search";
        break;
    }
  } else {
    switch (connection.status) {
      case "pending_auth":
        colorClass = "bg-cyan-500";
        status = "Authentication required";
        break;
      case "syncing":
        colorClass = "bg-blue-500";
        status = "Syncing";
        isAnimated = true;
        break;
      case "error":
        colorClass = "bg-red-500";
        status = "Sync failed";
        break;
      case "active":
        colorClass = "bg-green-500";
        status = "Active";
        break;
      case "inactive":
        colorClass = "bg-gray-400";
        status = "Inactive";
        break;
      default:
        colorClass = "bg-gray-400";
        status = "Unknown";
    }
  }
  return /* @__PURE__ */ jsx(
    "span",
    {
      className: cn(
        "inline-flex size-2 rounded-full opacity-80",
        colorClass,
        isAnimated && "animate-pulse"
      ),
      title: status
    }
  );
}
function SourceConnectionsList({
  sourceConnections,
  selectedConnectionId,
  onSelectConnection,
  onAddSource
}) {
  if (sourceConnections.length === 0) {
    return /* @__PURE__ */ jsx(
      EmptyState,
      {
        icon: /* @__PURE__ */ jsx(Plug, { strokeWidth: 1.5 }),
        title: "No sources connected",
        description: "Connect your first data source to start syncing and searching your data",
        className: "rounded-lg border-2 border-dashed py-12",
        children: /* @__PURE__ */ jsxs(
          Button,
          {
            variant: "outline",
            onClick: onAddSource,
            className: "border-blue-500 bg-blue-50 text-blue-600 hover:border-blue-600 hover:bg-blue-100 dark:border-blue-500 dark:bg-blue-500/20 dark:text-blue-400 dark:hover:border-blue-400 dark:hover:bg-blue-500/30",
            children: [
              /* @__PURE__ */ jsx(Plus, { className: "mr-1.5 size-4", strokeWidth: 2 }),
              "Connect a source"
            ]
          }
        )
      }
    );
  }
  return /* @__PURE__ */ jsxs("div", { className: "flex flex-wrap gap-2", children: [
    sourceConnections.map((connection) => /* @__PURE__ */ jsxs(
      "div",
      {
        className: cn(
          "flex h-10 cursor-pointer items-center gap-2 overflow-hidden rounded-md border px-3 py-2 transition-all",
          selectedConnectionId === connection.id ? "border-blue-500 bg-blue-500/10 shadow-lg ring-2 shadow-blue-500/20 ring-blue-500/30" : "border-border hover:bg-muted"
        ),
        onClick: () => onSelectConnection(connection.id),
        children: [
          getConnectionStatusIndicator(connection),
          /* @__PURE__ */ jsx("div", { className: "flex size-5 flex-shrink-0 items-center justify-center overflow-hidden rounded-md", children: /* @__PURE__ */ jsx(
            "img",
            {
              src: getAppIconUrl(connection.short_name),
              alt: connection.name,
              className: "size-5 object-contain"
            }
          ) }),
          /* @__PURE__ */ jsx("div", { className: "min-w-0 flex-1", children: /* @__PURE__ */ jsx("span", { className: "text-foreground block truncate text-sm font-medium", children: connection.name }) }),
          connection.auth?.authenticated && !connection.federated_search && (connection.entities?.total_entities ?? 0) >= 0 && /* @__PURE__ */ jsx("span", { className: "text-muted-foreground ml-1 flex-shrink-0 text-xs tabular-nums", children: (connection.entities?.total_entities ?? 0).toLocaleString() })
        ]
      },
      connection.id
    )),
    /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 100, children: /* @__PURE__ */ jsxs(Tooltip, { children: [
      /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsxs(
        "div",
        {
          className: cn(
            "flex h-10 cursor-pointer items-center gap-2 overflow-hidden rounded-md border border-dashed px-3 py-2 transition-all",
            "border-blue-500/30 bg-blue-500/5 hover:border-blue-400/40 hover:bg-blue-500/15"
          ),
          onClick: onAddSource,
          children: [
            /* @__PURE__ */ jsx(Plus, { className: "size-5 text-blue-500", strokeWidth: 1.5 }),
            /* @__PURE__ */ jsx("span", { className: "text-foreground text-sm font-medium", children: "Add Source" })
          ]
        }
      ) }),
      /* @__PURE__ */ jsx(TooltipContent, { children: /* @__PURE__ */ jsx("p", { children: "Add a new source to this collection" }) })
    ] }) })
  ] });
}
function PythonIcon({ className }) {
  return /* @__PURE__ */ jsxs(
    "svg",
    {
      viewBox: "0 0 24 24",
      fill: "currentColor",
      className,
      xmlns: "http://www.w3.org/2000/svg",
      children: [
        /* @__PURE__ */ jsx("path", { d: "M11.914 0C5.82 0 6.2 2.656 6.2 2.656l.007 2.752h5.814v.826H3.9S0 5.789 0 11.969c0 6.18 3.403 5.96 3.403 5.96h2.03v-2.867s-.109-3.42 3.35-3.42h5.766s3.24.052 3.24-3.148V3.202S18.28 0 11.914 0zM8.708 1.85c.578 0 1.048.473 1.048 1.053s-.47 1.052-1.048 1.052c-.579 0-1.048-.473-1.048-1.052 0-.58.47-1.053 1.048-1.053z" }),
        /* @__PURE__ */ jsx("path", { d: "M12.086 24c6.093 0 5.713-2.656 5.713-2.656l-.007-2.752h-5.814v-.826h8.121s3.9.445 3.9-5.735c0-6.18-3.402-5.96-3.402-5.96h-2.03v2.867s.109 3.42-3.35 3.42H9.45s-3.24-.052-3.24 3.148v5.292S5.72 24 12.086 24zm3.206-1.85c-.579 0-1.048-.473-1.048-1.053s.47-1.052 1.048-1.052c.578 0 1.048.473 1.048 1.052 0 .58-.47 1.053-1.048 1.053z" })
      ]
    }
  );
}
function NodeIcon({ className }) {
  return /* @__PURE__ */ jsx(
    "svg",
    {
      viewBox: "0 0 24 24",
      fill: "currentColor",
      className,
      xmlns: "http://www.w3.org/2000/svg",
      children: /* @__PURE__ */ jsx("path", { d: "M11.998 24c-.321 0-.641-.084-.922-.247l-2.936-1.737c-.438-.245-.224-.332-.08-.383.585-.203.703-.25 1.328-.604.066-.037.152-.023.22.017l2.256 1.339a.29.29 0 00.272 0l8.795-5.076a.277.277 0 00.134-.238V6.921a.282.282 0 00-.137-.242l-8.791-5.072a.278.278 0 00-.271 0L3.075 6.68a.281.281 0 00-.139.24v10.15c0 .099.053.19.137.239l2.409 1.392c1.307.654 2.108-.116 2.108-.89V7.787c0-.142.114-.253.256-.253h1.115c.139 0 .255.112.255.253v10.021c0 1.745-.95 2.745-2.604 2.745-.509 0-.909 0-2.026-.55l-2.304-1.326A1.85 1.85 0 011.36 17.07V6.921c0-.679.362-1.312.949-1.653l8.795-5.082a1.929 1.929 0 011.891 0l8.794 5.082a1.85 1.85 0 01.951 1.653v10.15a1.852 1.852 0 01-.951 1.652l-8.794 5.078c-.28.163-.599.247-.92.247" })
    }
  );
}
function McpIcon({ className }) {
  return /* @__PURE__ */ jsx(
    "svg",
    {
      viewBox: "0 0 24 24",
      fill: "currentColor",
      className,
      xmlns: "http://www.w3.org/2000/svg",
      children: /* @__PURE__ */ jsx("path", { d: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" })
    }
  );
}
function ApiIntegrationModal({
  collectionReadableId,
  query,
  searchConfig,
  filter,
  apiKey = "YOUR_API_KEY"
}) {
  const [activeTab, setActiveTab] = useState("rest");
  const [copied, setCopied] = useState(false);
  const snippets = useMemo(() => {
    const apiUrl = `${API_BASE_URL}/collections/${collectionReadableId}/search`;
    const searchQuery = query || "Ask a question about your data";
    const escapeForJson = (str) => str.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
    const escapeForPython = (str) => str.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
    let parsedFilter = null;
    if (filter) {
      try {
        parsedFilter = JSON.parse(filter);
      } catch {
        parsedFilter = null;
      }
    }
    const requestBody = {
      query: searchQuery,
      retrieval_strategy: searchConfig?.search_method || "hybrid",
      expand_query: searchConfig?.expansion_strategy !== "no_expansion",
      ...parsedFilter ? { filter: parsedFilter } : {},
      interpret_filters: searchConfig?.enable_query_interpretation || false,
      temporal_relevance: searchConfig?.recency_bias ?? 0.3,
      rerank: searchConfig?.enable_reranking ?? true,
      generate_answer: searchConfig?.response_type === "completion",
      limit: 20,
      offset: 0
    };
    const jsonBody = JSON.stringify(requestBody, null, 2).split("\n").map((line, index, array) => {
      if (index === 0) return line;
      if (index === array.length - 1) return "  " + line;
      return "  " + line;
    }).join("\n");
    const interpretNote = searchConfig?.enable_query_interpretation ? `# Note: interpret_filters is enabled, which may automatically add
# additional filters extracted from your natural language query.
# The filter shown below is your manual filter only.

` : "";
    const curlSnippet = `${interpretNote}curl -X 'POST' \\
  '${apiUrl}' \\
  -H 'accept: application/json' \\
  -H 'x-api-key: ${apiKey}' \\
  -H 'Content-Type: application/json' \\
  -d '${jsonBody}'`;
    const pythonFilterStr = parsedFilter ? JSON.stringify(parsedFilter, null, 4).split("\n").map((line, index) => index === 0 ? line : "        " + line).join("\n") : null;
    const pythonRequestParams = [
      `        query="${escapeForPython(searchQuery)}"`,
      `        retrieval_strategy=RetrievalStrategy.${(searchConfig?.search_method || "hybrid").toUpperCase()}`,
      `        expand_query=${searchConfig?.expansion_strategy !== "no_expansion" ? "True" : "False"}`,
      ...pythonFilterStr ? [`        filter=${pythonFilterStr}`] : [],
      `        interpret_filters=${searchConfig?.enable_query_interpretation ? "True" : "False"}`,
      `        temporal_relevance=${searchConfig?.recency_bias ?? 0}`,
      `        rerank=${searchConfig?.enable_reranking ?? true ? "True" : "False"}`,
      `        generate_answer=${searchConfig?.response_type === "completion" ? "True" : "False"}`,
      `        limit=1000`,
      `        offset=0`
    ];
    const pythonInterpretNote = searchConfig?.enable_query_interpretation ? `# Note: interpret_filters is enabled, which may automatically add
# additional filters extracted from your natural language query.
# The filter shown below is your manual filter only.

` : "";
    const pythonSnippet = `${pythonInterpretNote}from airweave import AirweaveSDK, SearchRequest, RetrievalStrategy

client = AirweaveSDK(
    api_key="${apiKey}",
)

result = client.collections.search(
    readable_id="${collectionReadableId}",
    request=SearchRequest(
${pythonRequestParams.join(",\n")}
    ),
)

print(result.completion)  # AI-generated answer (if generate_answer=True)
print(len(result.results))  # Number of results`;
    const nodeFilterStr = parsedFilter ? JSON.stringify(parsedFilter, null, 4).split("\n").map((line, index) => index === 0 ? line : "            " + line).join("\n") : null;
    const nodeRequestParams = [
      `            query: "${escapeForJson(searchQuery)}"`,
      `            retrievalStrategy: "${searchConfig?.search_method || "hybrid"}"`,
      `            expandQuery: ${searchConfig?.expansion_strategy !== "no_expansion"}`,
      ...nodeFilterStr ? [`            filter: ${nodeFilterStr}`] : [],
      `            interpretFilters: ${searchConfig?.enable_query_interpretation || false}`,
      `            temporalRelevance: ${searchConfig?.recency_bias ?? 0}`,
      `            rerank: ${searchConfig?.enable_reranking ?? true}`,
      `            generateAnswer: ${searchConfig?.response_type === "completion"}`,
      `            limit: 1000`,
      `            offset: 0`
    ];
    const nodeInterpretNote = searchConfig?.enable_query_interpretation ? `// Note: interpretFilters is enabled, which may automatically add
// additional filters extracted from your natural language query.
// The filter shown below is your manual filter only.

` : "";
    const nodeSnippet = `${nodeInterpretNote}import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "${apiKey}" });

const result = await client.collections.search("${collectionReadableId}", {
    request: {
${nodeRequestParams.join(",\n")}
    }
});

console.log(result.completion);  // AI-generated answer (if generateAnswer=true)
console.log(result.results.length);  // Number of results`;
    const mcpSnippet = `{
  "mcpServers": {
    "airweave-${collectionReadableId}": {
      "command": "npx",
      "args": ["airweave-mcp-search"],
      "env": {
        "AIRWEAVE_API_KEY": "${apiKey}",
        "AIRWEAVE_COLLECTION": "${collectionReadableId}",
        "AIRWEAVE_BASE_URL": "${API_BASE_URL}"
      }
    }
  }
}`;
    return {
      curl: curlSnippet,
      python: pythonSnippet,
      node: nodeSnippet,
      mcp: mcpSnippet
    };
  }, [collectionReadableId, apiKey, searchConfig, query, filter]);
  const handleCopy = async () => {
    const codeMap = {
      rest: snippets.curl,
      python: snippets.python,
      node: snippets.node,
      mcp: snippets.mcp
    };
    await navigator.clipboard.writeText(codeMap[activeTab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return /* @__PURE__ */ jsx("div", { className: "mb-6 w-full", children: /* @__PURE__ */ jsxs("div", { className: "overflow-hidden rounded-lg border border-slate-700 bg-slate-900", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex w-fit space-x-1 overflow-x-auto border-b border-slate-700 p-2", children: [
      /* @__PURE__ */ jsxs(
        Button,
        {
          variant: "ghost",
          size: "sm",
          onClick: () => setActiveTab("rest"),
          className: cn(
            "flex items-center gap-2 rounded-md",
            activeTab === "rest" ? "bg-slate-800 text-slate-200" : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
          ),
          children: [
            /* @__PURE__ */ jsx(Terminal, { className: "size-4" }),
            /* @__PURE__ */ jsx("span", { children: "cURL" })
          ]
        }
      ),
      /* @__PURE__ */ jsxs(
        Button,
        {
          variant: "ghost",
          size: "sm",
          onClick: () => setActiveTab("python"),
          className: cn(
            "flex items-center gap-2 rounded-md",
            activeTab === "python" ? "bg-slate-800 text-slate-200" : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
          ),
          children: [
            /* @__PURE__ */ jsx(PythonIcon, { className: "size-4" }),
            /* @__PURE__ */ jsx("span", { children: "Python" })
          ]
        }
      ),
      /* @__PURE__ */ jsxs(
        Button,
        {
          variant: "ghost",
          size: "sm",
          onClick: () => setActiveTab("node"),
          className: cn(
            "flex items-center gap-2 rounded-md",
            activeTab === "node" ? "bg-slate-800 text-slate-200" : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
          ),
          children: [
            /* @__PURE__ */ jsx(NodeIcon, { className: "size-4" }),
            /* @__PURE__ */ jsx("span", { children: "Node.js" })
          ]
        }
      ),
      /* @__PURE__ */ jsxs(
        Button,
        {
          variant: "ghost",
          size: "sm",
          onClick: () => setActiveTab("mcp"),
          className: cn(
            "flex items-center gap-2 rounded-md",
            activeTab === "mcp" ? "bg-slate-800 text-slate-200" : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
          ),
          children: [
            /* @__PURE__ */ jsx(McpIcon, { className: "size-4" }),
            /* @__PURE__ */ jsx("span", { children: "MCP" })
          ]
        }
      )
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "relative h-[460px]", children: [
      /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between border-b border-slate-800 px-4 py-2", children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
          /* @__PURE__ */ jsxs(
            "span",
            {
              className: cn(
                "rounded px-1.5 py-0.5 text-xs text-white",
                activeTab === "rest" && "bg-amber-600",
                activeTab === "python" && "bg-blue-600",
                activeTab === "node" && "bg-blue-600",
                activeTab === "mcp" && "bg-purple-600"
              ),
              children: [
                activeTab === "rest" && "POST",
                activeTab === "python" && "SDK",
                activeTab === "node" && "SDK",
                activeTab === "mcp" && "CONFIG"
              ]
            }
          ),
          /* @__PURE__ */ jsxs("span", { className: "text-xs font-medium text-slate-300", children: [
            activeTab === "rest" && `/collections/${collectionReadableId}/search`,
            activeTab === "python" && "AirweaveSDK",
            activeTab === "node" && "AirweaveSDKClient",
            activeTab === "mcp" && "MCP Configuration"
          ] })
        ] }),
        /* @__PURE__ */ jsx(
          Button,
          {
            variant: "ghost",
            size: "sm",
            className: "size-6 p-0 text-slate-400 hover:text-white",
            onClick: handleCopy,
            children: copied ? /* @__PURE__ */ jsx(Check, { className: "size-3" }) : /* @__PURE__ */ jsx(Copy, { className: "size-3" })
          }
        )
      ] }),
      /* @__PURE__ */ jsx("div", { className: "h-[calc(100%-88px)] overflow-auto bg-black px-4 py-3", children: /* @__PURE__ */ jsxs("pre", { className: "font-mono text-xs text-slate-300", children: [
        activeTab === "rest" && snippets.curl,
        activeTab === "python" && snippets.python,
        activeTab === "node" && snippets.node,
        activeTab === "mcp" && snippets.mcp
      ] }) }),
      /* @__PURE__ */ jsx("div", { className: "border-t border-slate-800 px-4 py-2 text-xs text-slate-400", children: activeTab === "mcp" ? /* @__PURE__ */ jsx("span", { children: "→ Add this to your MCP client configuration file (e.g., ~/.config/Claude/claude_desktop_config.json)" }) : /* @__PURE__ */ jsxs("span", { children: [
        "→",
        " ",
        /* @__PURE__ */ jsx(
          "a",
          {
            href: "https://docs.airweave.ai/api-reference/collections/search-advanced-collections-readable-id-search-post",
            target: "_blank",
            rel: "noopener noreferrer",
            className: "text-blue-400 hover:underline",
            children: "Explore the full API documentation"
          }
        )
      ] }) })
    ] })
  ] }) });
}
function ResultCollapsibleSection({
  title,
  count,
  children,
  defaultExpanded = false,
  showCopyButton = false,
  copyText
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);
  const handleCopy = async (e) => {
    e.stopPropagation();
    if (!copyText) return;
    try {
      await navigator.clipboard.writeText(copyText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2e3);
    } catch (error) {
      console.error("Failed to copy:", error);
    }
  };
  return /* @__PURE__ */ jsxs("div", { className: "border-t", children: [
    /* @__PURE__ */ jsxs(
      "button",
      {
        onClick: () => setIsExpanded(!isExpanded),
        className: "text-muted-foreground hover:text-foreground hover:bg-muted/50 flex w-full items-center gap-2 px-4 py-2 text-[10px] font-semibold tracking-wider uppercase transition-all duration-200",
        children: [
          isExpanded ? /* @__PURE__ */ jsx(ChevronDown, { className: "size-3" }) : /* @__PURE__ */ jsx(ChevronRight, { className: "size-3" }),
          title,
          count !== void 0 && ` (${count})`
        ]
      }
    ),
    isExpanded && /* @__PURE__ */ jsxs("div", { className: "relative px-4 pb-3", children: [
      showCopyButton && copyText && /* @__PURE__ */ jsx(
        "button",
        {
          onClick: handleCopy,
          className: "text-muted-foreground hover:text-foreground hover:bg-muted absolute top-0 right-4 z-10 rounded-lg p-1.5 transition-all duration-200",
          title: "Copy content",
          children: copied ? /* @__PURE__ */ jsx(Check, { className: "size-3.5" }) : /* @__PURE__ */ jsx(Copy, { className: "size-3.5" })
        }
      ),
      children
    ] })
  ] });
}
function getScoreDisplay(score) {
  if (score === void 0) return null;
  const isNormalizedScore = score >= 0 && score <= 1;
  if (isNormalizedScore) {
    return {
      value: `${(score * 100).toFixed(1)}%`,
      color: score >= 0.7 ? "green" : score >= 0.5 ? "yellow" : "gray"
    };
  }
  return {
    value: score.toFixed(3),
    color: score >= 10 ? "green" : score >= 5 ? "yellow" : "gray"
  };
}
function ResultScoreBadge({ index, score }) {
  const scoreDisplay = getScoreDisplay(score);
  if (!scoreDisplay) return null;
  const isNormalizedScore = score !== void 0 && score >= 0 && score <= 1;
  return /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 200, children: /* @__PURE__ */ jsxs(Tooltip, { children: [
    /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsxs(
      "div",
      {
        className: cn(
          "flex flex-shrink-0 cursor-help items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold whitespace-nowrap shadow-sm transition-all duration-200 hover:shadow-md",
          scoreDisplay.color === "green" && "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-400 dark:hover:bg-emerald-500/20",
          scoreDisplay.color === "yellow" && "border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-400 dark:hover:bg-amber-500/20",
          scoreDisplay.color === "gray" && "hover:bg-gray-150 border-gray-300 bg-gray-100 text-gray-600 dark:border-gray-600/50 dark:bg-gray-700/40 dark:text-gray-400 dark:hover:bg-gray-700/50"
        ),
        children: [
          /* @__PURE__ */ jsxs("span", { className: "font-bold tracking-wider opacity-70", children: [
            "#",
            index + 1
          ] }),
          /* @__PURE__ */ jsx("div", { className: "h-3 w-px opacity-30 dark:bg-gray-400" }),
          /* @__PURE__ */ jsx("span", { className: "font-mono tracking-tight", children: scoreDisplay.value })
        ]
      }
    ) }),
    /* @__PURE__ */ jsx(TooltipContent, { side: "left", children: /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
      /* @__PURE__ */ jsxs("div", { className: "text-[11px] font-bold tracking-wide", children: [
        "Result #",
        index + 1
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "text-[12px]", children: [
        /* @__PURE__ */ jsx("span", { className: "font-medium", children: "Similarity:" }),
        " ",
        /* @__PURE__ */ jsx("span", { className: "font-semibold", children: isNormalizedScore ? `${(score * 100).toFixed(1)}%` : score.toFixed(3) })
      ] }),
      /* @__PURE__ */ jsx("div", { className: "bg-border h-px w-full" }),
      /* @__PURE__ */ jsx("div", { className: "text-muted-foreground text-[11px] leading-relaxed", children: "Position determined by semantic reranking." })
    ] }) })
  ] }) });
}
const arePropsEqual = (prevProps, nextProps) => {
  return prevProps.index === nextProps.index && prevProps.result.id === nextProps.result.id && prevProps.result.score === nextProps.result.score;
};
function formatDate(dateString) {
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    const now = /* @__PURE__ */ new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1e3 * 60 * 60 * 24));
    const timeStr = date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true
    });
    if (diffDays === 0) return `Today at ${timeStr}`;
    if (diffDays === 1) return `Yesterday at ${timeStr}`;
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric"
    }) + " at " + timeStr;
  } catch {
    return dateString;
  }
}
function extractEntityType(rawEntityType, sourceName) {
  let entityTypeCore = rawEntityType.replace(/Entity$/, "");
  if (entityTypeCore && sourceName) {
    const normalizedSource = sourceName.replace(/[\s_-]/g, "");
    if (normalizedSource) {
      const prefixRegex = new RegExp(
        `^${normalizedSource.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`,
        "i"
      );
      const condensedEntity = entityTypeCore.replace(/[\s_-]/g, "");
      if (prefixRegex.test(condensedEntity)) {
        entityTypeCore = entityTypeCore.slice(normalizedSource.length);
      }
    }
  }
  return entityTypeCore ? entityTypeCore.replace(/([A-Z])/g, " $1").trim() || "Document" : "Document";
}
const EntityResultCardComponent = ({
  result,
  index
}) => {
  const payload = result.payload || result;
  const score = result.score;
  const systemMetadata = payload.airweave_system_metadata;
  const entityId = payload.entity_id || payload.id || payload._id;
  const sourceName = systemMetadata?.source_name || payload.source_name || "Unknown Source";
  const sourceIconUrl = getAppIconUrl(sourceName);
  const textualRepresentation = payload.textual_representation || "";
  const breadcrumbs = payload.breadcrumbs || [];
  const webUrl = payload.web_url;
  const url = payload.url;
  const openUrl = webUrl || url;
  const hasDownloadUrl = Boolean(url && webUrl && url !== webUrl);
  const title = payload.name || "Untitled";
  const rawEntityType = systemMetadata?.entity_type || "";
  const entityType = extractEntityType(rawEntityType, sourceName);
  const context = breadcrumbs.length > 0 ? breadcrumbs.map(
    (b) => typeof b === "string" ? b : b.name || ""
  ).filter(Boolean).join(" > ") : "";
  const relevantTimestamp = payload.updated_at || payload.created_at;
  const formattedSourceName = sourceName.split("_").map(
    (word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
  ).join(" ");
  const metadata = useMemo(() => {
    const filtered = {};
    const excludeKeys = [
      "entity_id",
      "id",
      "_id",
      "textual_representation",
      "name",
      "breadcrumbs",
      "url",
      "web_url",
      "airweave_system_metadata",
      "source_name",
      "created_at",
      "updated_at",
      "vector",
      "vectors"
    ];
    Object.entries(payload).forEach(([key, value]) => {
      if (!excludeKeys.includes(key) && value !== null && value !== void 0 && value !== "") {
        const formattedKey = key.split("_").map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
        filtered[formattedKey] = value;
      }
    });
    return filtered;
  }, [payload]);
  const hasMetadata = Object.keys(metadata).length > 0;
  return /* @__PURE__ */ jsxs(
    "div",
    {
      "data-entity-id": entityId,
      className: "group bg-card relative overflow-hidden rounded-xl border transition-all duration-300",
      children: [
        /* @__PURE__ */ jsx("div", { className: "border-b px-4 py-3", children: /* @__PURE__ */ jsxs("div", { className: "flex items-start justify-between gap-3", children: [
          /* @__PURE__ */ jsx("div", { className: "min-w-0 flex-1", children: /* @__PURE__ */ jsxs("div", { className: "flex items-start gap-2.5", children: [
            /* @__PURE__ */ jsx(
              "div",
              {
                className: "bg-muted flex size-8 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg",
                title: formattedSourceName,
                children: /* @__PURE__ */ jsx(
                  "img",
                  {
                    src: sourceIconUrl,
                    alt: formattedSourceName,
                    className: "size-full object-contain p-1.5",
                    onError: (e) => {
                      e.currentTarget.style.display = "none";
                    }
                  }
                )
              }
            ),
            /* @__PURE__ */ jsxs("div", { className: "min-w-0 flex-1 pt-0.5", children: [
              /* @__PURE__ */ jsxs("div", { className: "mb-1.5 flex flex-wrap items-center gap-2", children: [
                /* @__PURE__ */ jsx("h3", { className: "text-foreground text-[14px] leading-snug font-semibold tracking-tight break-words", children: title }),
                openUrl && /* @__PURE__ */ jsxs("div", { className: "flex flex-wrap items-center gap-2", children: [
                  /* @__PURE__ */ jsxs(
                    "a",
                    {
                      href: openUrl,
                      target: "_blank",
                      rel: "noopener noreferrer",
                      className: "inline-flex items-center gap-1.5 text-[12px] font-medium text-blue-600 transition-all duration-200 hover:gap-2 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300",
                      children: [
                        /* @__PURE__ */ jsx(ExternalLink, { className: "size-3" }),
                        "Open in ",
                        formattedSourceName
                      ]
                    }
                  ),
                  hasDownloadUrl && /* @__PURE__ */ jsxs(
                    "a",
                    {
                      href: url,
                      target: "_blank",
                      rel: "noopener noreferrer",
                      className: "inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 transition-all duration-200 hover:gap-1.5 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300",
                      children: [
                        /* @__PURE__ */ jsx(Link, { className: "size-3" }),
                        "Download original"
                      ]
                    }
                  )
                ] })
              ] }),
              /* @__PURE__ */ jsxs("div", { className: "mb-0 flex flex-wrap items-center gap-1", children: [
                /* @__PURE__ */ jsx("span", { className: "text-foreground bg-muted inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium", children: entityType }),
                context && context.length > 0 && /* @__PURE__ */ jsx("span", { className: "text-muted-foreground bg-muted/50 inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium", children: context }),
                relevantTimestamp && /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 200, children: /* @__PURE__ */ jsxs(Tooltip, { children: [
                  /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsxs("span", { className: "text-muted-foreground bg-muted/30 inline-flex cursor-help items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium", children: [
                    /* @__PURE__ */ jsx(Clock, { className: "size-3", strokeWidth: 1.5 }),
                    formatDate(relevantTimestamp)
                  ] }) }),
                  /* @__PURE__ */ jsx(TooltipContent, { side: "top", children: /* @__PURE__ */ jsxs("div", { className: "space-y-1", children: [
                    /* @__PURE__ */ jsx("div", { className: "text-[11px] font-bold tracking-wide", children: payload.updated_at ? "Last Updated" : "Created" }),
                    /* @__PURE__ */ jsx("div", { className: "font-mono text-[12px]", children: new Date(relevantTimestamp).toLocaleString(
                      "en-US",
                      {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                        hour12: true
                      }
                    ) })
                  ] }) })
                ] }) })
              ] })
            ] })
          ] }) }),
          /* @__PURE__ */ jsx(ResultScoreBadge, { index, score })
        ] }) }),
        textualRepresentation && /* @__PURE__ */ jsx(
          ResultCollapsibleSection,
          {
            title: "Preview",
            showCopyButton: true,
            copyText: textualRepresentation,
            children: /* @__PURE__ */ jsx("div", { className: "text-foreground max-h-[200px] overflow-hidden pr-8", children: /* @__PURE__ */ jsx("p", { className: "text-[13px] leading-relaxed whitespace-pre-wrap", children: textualRepresentation.length > 500 ? textualRepresentation.substring(0, 500) + "..." : textualRepresentation }) })
          }
        ),
        hasMetadata && /* @__PURE__ */ jsx(
          ResultCollapsibleSection,
          {
            title: "Properties",
            count: Object.keys(metadata).length,
            children: /* @__PURE__ */ jsx("div", { className: "bg-muted/30 -mx-4 px-4 pb-2.5", children: /* @__PURE__ */ jsx("div", { className: "grid grid-cols-2 gap-x-6 gap-y-2.5", children: Object.entries(metadata).slice(0, 8).map(([key, value]) => /* @__PURE__ */ jsx("div", { className: "flex flex-col gap-1", children: /* @__PURE__ */ jsxs("div", { className: "flex items-start gap-2.5", children: [
              /* @__PURE__ */ jsx("span", { className: "text-muted-foreground min-w-[80px] pt-0.5 text-[10px] font-semibold tracking-wider uppercase", children: key }),
              /* @__PURE__ */ jsx("span", { className: "text-muted-foreground flex-1 text-[12px] leading-snug break-words", children: typeof value === "object" ? JSON.stringify(value) : String(value).length > 100 ? String(value).substring(0, 100) + "..." : String(value) })
            ] }) }, key)) }) })
          }
        )
      ]
    }
  );
};
const EntityResultCard = React__default.memo(
  EntityResultCardComponent,
  arePropsEqual
);
const EXAMPLE_FILTER = `{
  "must": [
    {
      "key": "source_name",
      "match": {
        "value": "slack"
      }
    }
  ]
}`;
function JsonFilterEditor({
  value,
  onChange,
  height = "160px",
  className
}) {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const [localValue, setLocalValue] = useState(value || EXAMPLE_FILTER);
  const [validationError, setValidationError] = useState(null);
  const [isValidating, setIsValidating] = useState(false);
  const [filterSchema, setFilterSchema] = useState(null);
  const [copied, setCopied] = useState(false);
  const validationTimeoutRef = useRef(null);
  const copyTimeoutRef = useRef(null);
  const initializedRef = useRef(false);
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    if (!value && localValue === EXAMPLE_FILTER) {
      onChange(EXAMPLE_FILTER, true);
    }
  }, [value, localValue, onChange]);
  useEffect(() => {
    const fetchSchema = async () => {
      try {
        const token = await getAccessTokenSilently();
        const response = await fetch(
          `${API_BASE_URL}/collections/internal/filter-schema`,
          {
            headers: getAuthHeaders(token, organization?.id || "")
          }
        );
        if (response.ok) {
          const schema = await response.json();
          if (schema && typeof schema === "object") {
            setFilterSchema(schema);
          }
        }
      } catch (error) {
        console.error("Error fetching filter schema:", error);
      }
    };
    if (organization) {
      fetchSchema();
    }
    return () => {
      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current);
      }
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
    };
  }, [getAccessTokenSilently, organization]);
  const validateFilter = useCallback(
    (filterValue) => {
      if (!filterValue.trim()) {
        return { isValid: true, error: null };
      }
      let parsed;
      try {
        parsed = JSON.parse(filterValue);
      } catch {
        return { isValid: false, error: "Invalid JSON syntax" };
      }
      if (!filterSchema) {
        return { isValid: true, error: null };
      }
      if (typeof parsed !== "object" || parsed === null) {
        return { isValid: false, error: "Filter must be an object" };
      }
      const validKeys = ["must", "should", "must_not", "min_should"];
      const keys = Object.keys(parsed);
      if (keys.length === 0) {
        return { isValid: true, error: null };
      }
      const hasValidKey = keys.some((k) => validKeys.includes(k));
      if (!hasValidKey && keys.length > 0) {
        return {
          isValid: false,
          error: `Filter should have one of: ${validKeys.join(", ")}`
        };
      }
      return { isValid: true, error: null };
    },
    [filterSchema]
  );
  useEffect(() => {
    if (localValue && filterSchema) {
      const validation = validateFilter(localValue);
      setValidationError(validation.error);
    }
  }, [filterSchema, validateFilter, localValue]);
  const handleChange = useCallback(
    (newValue) => {
      setLocalValue(newValue);
      if (!newValue.trim()) {
        setValidationError(null);
        setIsValidating(false);
        onChange("", true);
        return;
      }
      setIsValidating(true);
      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current);
      }
      validationTimeoutRef.current = setTimeout(() => {
        const validation = validateFilter(newValue);
        setValidationError(validation.error);
        setIsValidating(false);
        onChange(newValue, validation.isValid);
      }, 500);
    },
    [validateFilter, onChange]
  );
  const handleCopy = useCallback(() => {
    const textToCopy = localValue.trim();
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
      copyTimeoutRef.current = setTimeout(() => {
        setCopied(false);
      }, 2e3);
    }
  }, [localValue]);
  return /* @__PURE__ */ jsxs("div", { className: cn("space-y-2", className), children: [
    /* @__PURE__ */ jsxs("div", { className: "relative", children: [
      /* @__PURE__ */ jsx(
        "textarea",
        {
          value: localValue,
          onChange: (e) => handleChange(e.target.value),
          className: cn(
            "w-full resize-none rounded-md border p-3 pr-20 font-mono text-xs transition-colors",
            "bg-slate-900 text-slate-100 placeholder:text-slate-600",
            validationError ? "border-red-500 focus:border-red-500" : "border-slate-700 focus:border-blue-500",
            "focus:ring-1 focus:outline-none",
            validationError ? "focus:ring-red-500" : "focus:ring-blue-500"
          ),
          style: { height },
          spellCheck: false
        }
      ),
      /* @__PURE__ */ jsxs("div", { className: "absolute top-2 right-2 flex items-center gap-2", children: [
        /* @__PURE__ */ jsx(
          "button",
          {
            type: "button",
            onClick: handleCopy,
            className: "rounded p-1 text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-200",
            title: "Copy filter",
            children: copied ? /* @__PURE__ */ jsx(Check, { className: "size-3.5 text-green-500" }) : /* @__PURE__ */ jsx(Copy, { className: "size-3.5" })
          }
        ),
        isValidating ? /* @__PURE__ */ jsx("div", { className: "text-xs text-slate-400", children: "Validating..." }) : validationError ? /* @__PURE__ */ jsx(CircleAlert, { className: "size-4 text-red-500" }) : localValue.trim() ? /* @__PURE__ */ jsx(CircleCheck, { className: "size-4 text-green-500" }) : null
      ] })
    ] }),
    validationError && /* @__PURE__ */ jsxs("div", { className: "flex items-start gap-1 text-xs text-red-500", children: [
      /* @__PURE__ */ jsx(CircleAlert, { className: "mt-0.5 size-3 shrink-0" }),
      /* @__PURE__ */ jsx("span", { children: validationError })
    ] })
  ] });
}
function useDragInteraction({
  onDragStart,
  onDrag,
  onDragEnd,
  computeValue
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [currentValue, setCurrentValue] = useState(null);
  const handleMouseDown = useCallback(
    (event) => {
      event.preventDefault();
      setIsDragging(true);
      const value = computeValue(event);
      setCurrentValue(value);
      onDragStart?.(event);
      onDrag(event.nativeEvent, value);
    },
    [computeValue, onDrag, onDragStart]
  );
  useEffect(() => {
    if (!isDragging) return;
    const handleMouseMove = (event) => {
      const value = computeValue(event);
      setCurrentValue(value);
      onDrag(event, value);
    };
    const handleMouseUp = () => {
      setIsDragging(false);
      setCurrentValue(null);
      onDragEnd?.();
    };
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, computeValue, onDrag, onDragEnd]);
  return {
    isDragging,
    onMouseDown: handleMouseDown,
    currentValue
  };
}
function useSyncProp(propValue) {
  const [localValue, setLocalValue] = useState(propValue);
  useEffect(() => {
    setLocalValue(propValue);
  }, [propValue]);
  return [localValue, setLocalValue];
}
function RecencyBiasSlider({
  value,
  onChange,
  className
}) {
  const [localValue, setLocalValue] = useSyncProp(value);
  const sliderRef = useRef(null);
  const getPositionFromValue = (val) => {
    return Math.max(0, Math.min(100, val * 100));
  };
  const computeValue = useCallback(
    (event) => {
      if (!sliderRef.current) return 0;
      const rect = sliderRef.current.getBoundingClientRect();
      const position2 = (event.clientX - rect.left) / rect.width;
      const clampedPosition = Math.max(0, Math.min(1, position2));
      return Math.round(clampedPosition * 10) / 10;
    },
    []
  );
  const { isDragging, onMouseDown } = useDragInteraction({
    computeValue,
    onDrag: (_event, newValue) => {
      setLocalValue(newValue);
      onChange(newValue);
    }
  });
  const position = getPositionFromValue(localValue);
  return /* @__PURE__ */ jsxs("div", { className: cn("space-y-1.5", className), children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between", children: [
      /* @__PURE__ */ jsx("span", { className: "text-[10px] text-white/60", children: "0" }),
      /* @__PURE__ */ jsx("div", { className: "text-xs font-semibold text-white", children: localValue.toFixed(1) }),
      /* @__PURE__ */ jsx("span", { className: "text-[10px] text-white/60", children: "1" })
    ] }),
    /* @__PURE__ */ jsxs(
      "div",
      {
        ref: sliderRef,
        className: "relative h-1.5 cursor-pointer rounded-full bg-gray-700",
        onMouseDown,
        children: [
          /* @__PURE__ */ jsx(
            "div",
            {
              className: cn(
                "absolute top-0 left-0 h-full rounded-full",
                localValue > 0 ? "bg-primary" : "bg-gray-600"
              ),
              style: {
                width: `${position}%`,
                transition: isDragging ? "none" : "width 0.1s ease-out"
              }
            }
          ),
          /* @__PURE__ */ jsx(
            "div",
            {
              className: cn(
                "absolute top-1/2 size-4 -translate-y-1/2 cursor-grab rounded-full shadow-md",
                isDragging && "cursor-grabbing",
                localValue > 0 ? "bg-primary border border-white" : "border border-gray-400 bg-white"
              ),
              style: {
                left: `${position}%`,
                transform: `translateX(-50%) translateY(-50%)`,
                transition: isDragging ? "none" : "left 0.1s ease-out, background-color 0.2s"
              },
              onMouseDown
            }
          )
        ]
      }
    )
  ] });
}
class HandledStreamError extends Error {
  constructor(message) {
    super(message);
    this.name = "HandledStreamError";
  }
}
function useSearchStream() {
  const abortRef = useRef(null);
  const searchSeqRef = useRef(0);
  const cancelSearch = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);
  const executeSearch = useCallback(
    async ({
      collectionId,
      requestBody,
      token,
      orgId,
      onStreamEvent,
      onSuccess,
      onError
    }) => {
      cancelSearch();
      const mySeq = ++searchSeqRef.current;
      const abortController = new AbortController();
      abortRef.current = abortController;
      const startTime = performance.now();
      try {
        const response = await fetch(
          `${API_BASE_URL}/collections/${collectionId}/search/stream`,
          {
            method: "POST",
            headers: getAuthHeaders(token, orgId),
            body: JSON.stringify(requestBody),
            signal: abortController.signal
          }
        );
        if (!response.ok || !response.body) {
          const errorText = await response.text().catch(() => "");
          throw new Error(
            errorText || `Stream failed: ${response.status} ${response.statusText}`
          );
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let latestResults = [];
        let latestCompletion = null;
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          if (searchSeqRef.current !== mySeq) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() || "";
          for (const frame of frames) {
            const dataLines = frame.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim());
            if (dataLines.length === 0) continue;
            const payloadStr = dataLines.join("\n");
            let event;
            try {
              event = JSON.parse(payloadStr);
            } catch {
              continue;
            }
            onStreamEvent?.(event);
            switch (event.type) {
              case "results":
                if (Array.isArray(event.results)) {
                  latestResults = event.results;
                }
                break;
              case "completion_done":
                if (typeof event.text === "string") {
                  latestCompletion = event.text;
                }
                break;
              case "error": {
                const endTime = performance.now();
                const responseTime = Math.round(endTime - startTime);
                const errorEvent = event;
                const errorMessage = errorEvent.message || "Streaming error";
                const isTransient = errorEvent.transient === true;
                onError(new Error(errorMessage), responseTime, isTransient);
                throw new HandledStreamError(errorMessage);
              }
              case "done": {
                const endTime = performance.now();
                const responseTime = Math.round(endTime - startTime);
                onSuccess(
                  {
                    completion: latestCompletion,
                    results: latestResults,
                    responseTime
                  },
                  responseTime
                );
                break;
              }
            }
          }
        }
      } catch (error) {
        const err = error;
        if (err.name === "AbortError") ;
        else if (err instanceof HandledStreamError) ;
        else {
          const endTime = performance.now();
          const responseTime = Math.round(endTime - startTime);
          onError(err, responseTime, true);
        }
      } finally {
        if (searchSeqRef.current === mySeq && abortRef.current === abortController) {
          abortRef.current = null;
        }
      }
    },
    [cancelSearch]
  );
  return {
    executeSearch,
    cancelSearch,
    isActive: () => abortRef.current !== null
  };
}
const TOOLTIP_CLOSE_DELAY = 100;
function useTooltipManager() {
  const [openTooltip, setOpenTooltip] = useState(null);
  const [hoveredContent, setHoveredContent] = useState(null);
  const timeoutRef = useRef(null);
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);
  const handleMouseEnter = useCallback((tooltipId) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setOpenTooltip(tooltipId);
  }, []);
  const handleMouseLeave = useCallback(
    (tooltipId) => {
      if (hoveredContent !== tooltipId) {
        timeoutRef.current = setTimeout(() => {
          setOpenTooltip((prev) => prev === tooltipId ? null : prev);
        }, TOOLTIP_CLOSE_DELAY);
      }
    },
    [hoveredContent]
  );
  const handleContentMouseEnter = useCallback((tooltipId) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setHoveredContent(tooltipId);
    setOpenTooltip(tooltipId);
  }, []);
  const handleContentMouseLeave = useCallback((tooltipId) => {
    setHoveredContent(null);
    timeoutRef.current = setTimeout(() => {
      setOpenTooltip((prev) => prev === tooltipId ? null : prev);
    }, TOOLTIP_CLOSE_DELAY);
  }, []);
  const forceOpen = useCallback((tooltipId) => {
    setOpenTooltip(tooltipId);
  }, []);
  return {
    openTooltip,
    handleMouseEnter,
    handleMouseLeave,
    handleContentMouseEnter,
    handleContentMouseLeave,
    forceOpen
  };
}
function CodeButton({ onClick }) {
  return /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 0, children: /* @__PURE__ */ jsxs(Tooltip, { children: [
    /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(
      "button",
      {
        type: "button",
        onClick,
        className: "absolute top-2 right-2 z-20 flex size-8 items-center justify-center rounded-md border border-dashed border-blue-500/30 bg-blue-500/10 shadow-sm transition-all hover:border-blue-400/40 hover:bg-blue-500/15",
        title: "View integration code",
        children: /* @__PURE__ */ jsx(CodeXml, { className: "size-4 text-blue-400" })
      }
    ) }),
    /* @__PURE__ */ jsxs(TooltipContent, { side: "left", sideOffset: 8, children: [
      /* @__PURE__ */ jsx("p", { className: "font-semibold", children: "Call the Search API" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-xs", children: "Open a ready-to-use snippet for JS or Python." })
    ] })
  ] }) });
}
function SearchInput({
  value,
  onChange,
  onSubmit,
  isDisabled,
  isSearching,
  usageLimit
}) {
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isDisabled && !isSearching && value.trim()) {
        onSubmit();
      }
    }
  };
  if (isDisabled && usageLimit) {
    if (usageLimit.reason === "no_sources") {
      return /* @__PURE__ */ jsx(
        "textarea",
        {
          value,
          onChange: (e) => onChange(e.target.value),
          onKeyDown: (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
            }
          },
          placeholder: "Connect a source to start searching",
          disabled: true,
          className: "placeholder:text-muted-foreground h-20 w-full resize-none overflow-y-auto rounded-xl bg-transparent px-2 py-1.5 pr-28 text-sm leading-relaxed opacity-60 outline-none"
        }
      );
    }
    return /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 0, children: /* @__PURE__ */ jsxs(Tooltip, { children: [
      /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx("div", { children: /* @__PURE__ */ jsx(
        "textarea",
        {
          value,
          onChange: (e) => onChange(e.target.value),
          onKeyDown: (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
            }
          },
          placeholder: "Ask a question about your data",
          disabled: true,
          className: "placeholder:text-muted-foreground h-20 w-full resize-none overflow-y-auto rounded-xl bg-transparent px-2 py-1.5 pr-28 text-sm leading-relaxed opacity-60 outline-none"
        }
      ) }) }),
      /* @__PURE__ */ jsx(TooltipContent, { className: "max-w-xs", children: /* @__PURE__ */ jsx("p", { className: "text-sm", children: usageLimit.isChecking ? "Checking usage..." : usageLimit.reason === "usage_limit_exceeded" ? /* @__PURE__ */ jsxs(Fragment, { children: [
        "Query limit reached.",
        " ",
        /* @__PURE__ */ jsx(
          "a",
          {
            href: "/organization/settings?tab=billing",
            className: "underline",
            children: "Upgrade your plan"
          }
        ),
        " ",
        "to continue searching."
      ] }) : usageLimit.reason === "payment_required" ? /* @__PURE__ */ jsxs(Fragment, { children: [
        "Billing issue detected.",
        " ",
        /* @__PURE__ */ jsx(
          "a",
          {
            href: "/organization/settings?tab=billing",
            className: "underline",
            children: "Update billing"
          }
        ),
        " ",
        "to continue searching."
      ] }) : "Search is currently disabled." }) })
    ] }) });
  }
  return /* @__PURE__ */ jsx(
    "textarea",
    {
      value,
      onChange: (e) => onChange(e.target.value),
      onKeyDown: handleKeyDown,
      placeholder: "Ask a question about your data",
      className: "placeholder:text-muted-foreground h-20 w-full resize-none overflow-y-auto rounded-xl bg-transparent px-2 py-1.5 pr-28 text-sm leading-relaxed outline-none"
    }
  );
}
const METHODS = [
  {
    id: "hybrid",
    icon: /* @__PURE__ */ jsx(GitMerge, { className: "size-4", strokeWidth: 1.5 }),
    title: "Hybrid Search",
    description: "Combines semantic and keyword signals"
  },
  {
    id: "neural",
    icon: /* @__PURE__ */ jsx(ChartScatter, { className: "size-4", strokeWidth: 1.5 }),
    title: "Neural Search",
    description: "Pure semantic matching using embeddings"
  },
  {
    id: "keyword",
    icon: /* @__PURE__ */ jsx(Type, { className: "size-4", strokeWidth: 1.5 }),
    title: "Keyword Search",
    description: "BM25 keyword matching"
  }
];
function SearchMethodSelector({
  value,
  onChange,
  openTooltip,
  onMouseEnter,
  onMouseLeave,
  onContentMouseEnter,
  onContentMouseLeave
}) {
  return /* @__PURE__ */ jsx("div", { className: "inline-block h-7", children: /* @__PURE__ */ jsx("div", { className: "bg-background relative grid h-full grid-cols-3 items-stretch gap-0.5 overflow-hidden rounded-md border p-0.5", children: METHODS.map((method) => /* @__PURE__ */ jsxs(Tooltip, { open: openTooltip === method.id, children: [
    /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(
      "button",
      {
        type: "button",
        onClick: () => onChange(method.id),
        onMouseEnter: () => onMouseEnter(method.id),
        onMouseLeave: () => onMouseLeave(method.id),
        className: cn(
          "flex aspect-square h-full items-center justify-center rounded-md border transition-all",
          value === method.id ? "border-primary text-primary" : "text-foreground hover:bg-muted border-transparent"
        ),
        children: method.icon
      }
    ) }),
    /* @__PURE__ */ jsxs(
      TooltipContent,
      {
        side: "bottom",
        onMouseEnter: () => onContentMouseEnter(method.id),
        onMouseLeave: () => onContentMouseLeave(method.id),
        children: [
          /* @__PURE__ */ jsx("p", { className: "font-semibold", children: method.title }),
          /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-xs", children: method.description }),
          /* @__PURE__ */ jsx("div", { className: "border-border mt-2 border-t pt-2", children: /* @__PURE__ */ jsx(
            "a",
            {
              href: "https://docs.airweave.ai/search#search-method",
              target: "_blank",
              rel: "noreferrer",
              className: "text-xs text-blue-400 hover:underline",
              children: "Docs"
            }
          ) })
        ]
      }
    )
  ] }, method.id)) }) });
}
function SearchSubmitButton({
  isSearching,
  hasQuery,
  queriesAllowed,
  isCheckingUsage,
  canRetry,
  retryMessage,
  onSubmit,
  onCancel,
  onRetry
}) {
  const handleClick = () => {
    if (isSearching) {
      onCancel();
    } else if (canRetry) {
      onRetry();
    } else {
      onSubmit();
    }
  };
  const getTooltipText = () => {
    if (isSearching) return "Stop search";
    if (canRetry)
      return retryMessage || "Connection interrupted. Click to retry.";
    if (!hasQuery) return "Type a question to enable";
    if (!queriesAllowed) return "Query limit reached";
    if (isCheckingUsage) return "Checking usage...";
    return "Send query";
  };
  const getIcon = () => {
    if (isSearching) {
      return /* @__PURE__ */ jsx(Square, { className: "size-4 text-red-500" });
    }
    if (canRetry) {
      return /* @__PURE__ */ jsx(RefreshCw, { className: "text-muted-foreground size-4" });
    }
    return /* @__PURE__ */ jsx(ArrowUp, { className: "size-4" });
  };
  return /* @__PURE__ */ jsx(TooltipProvider, { delayDuration: 0, children: /* @__PURE__ */ jsxs(Tooltip, { children: [
    /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(
      Button,
      {
        variant: "outline",
        size: "icon",
        className: "size-8",
        onClick: handleClick,
        disabled: isSearching ? false : !hasQuery || !queriesAllowed || isCheckingUsage,
        children: getIcon()
      }
    ) }),
    /* @__PURE__ */ jsx(TooltipContent, { children: getTooltipText() })
  ] }) });
}
function ToggleButton({
  id,
  icon,
  isActive,
  onClick,
  tooltip,
  openTooltip,
  onMouseEnter,
  onMouseLeave,
  onContentMouseEnter,
  onContentMouseLeave
}) {
  return /* @__PURE__ */ jsxs(Tooltip, { open: openTooltip === id, children: [
    /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(
      "div",
      {
        onMouseEnter: () => onMouseEnter(id),
        onMouseLeave: () => onMouseLeave(id),
        className: cn(
          "h-7 w-8 overflow-hidden rounded-md border p-0",
          isActive ? "border-primary" : "border-border/50"
        ),
        children: /* @__PURE__ */ jsx(
          "button",
          {
            type: "button",
            onClick,
            className: cn(
              "flex size-full items-center justify-center rounded-md transition-all",
              isActive ? "text-primary hover:bg-primary/10" : "text-foreground hover:bg-muted"
            ),
            children: icon
          }
        )
      }
    ) }),
    /* @__PURE__ */ jsxs(
      TooltipContent,
      {
        side: "bottom",
        onMouseEnter: () => onContentMouseEnter(id),
        onMouseLeave: () => onContentMouseLeave(id),
        children: [
          /* @__PURE__ */ jsx("p", { className: "font-semibold", children: tooltip.title }),
          /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-xs", children: tooltip.description }),
          tooltip.docsUrl && /* @__PURE__ */ jsx("div", { className: "border-border mt-2 border-t pt-2", children: /* @__PURE__ */ jsx(
            "a",
            {
              href: tooltip.docsUrl,
              target: "_blank",
              rel: "noreferrer",
              className: "text-xs text-blue-400 hover:underline",
              children: "Docs"
            }
          ) })
        ]
      }
    )
  ] });
}
function SearchTogglesPanel({
  toggles,
  onToggle,
  filterJson,
  onFilterChange,
  recencyBiasValue,
  onRecencyBiasChange,
  openTooltip,
  onMouseEnter,
  onMouseLeave,
  onContentMouseEnter,
  onContentMouseLeave
}) {
  return /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1.5", children: [
    /* @__PURE__ */ jsx(
      ToggleButton,
      {
        id: "queryExpansion",
        icon: /* @__PURE__ */ jsx(Layers, { className: "size-4", strokeWidth: 1.5 }),
        isActive: toggles.queryExpansion,
        onClick: () => onToggle("queryExpansion"),
        tooltip: {
          title: "Query Expansion",
          description: "Generates similar versions of your query",
          docsUrl: "https://docs.airweave.ai/search#query-expansion"
        },
        openTooltip,
        onMouseEnter,
        onMouseLeave,
        onContentMouseEnter,
        onContentMouseLeave
      }
    ),
    /* @__PURE__ */ jsxs(Tooltip, { open: openTooltip === "filter", children: [
      /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(
        "div",
        {
          onMouseEnter: () => onMouseEnter("filter"),
          onMouseLeave: () => onMouseLeave("filter"),
          className: cn(
            "h-7 w-8 overflow-hidden rounded-md border p-0",
            toggles.filter ? "border-primary" : "border-border/50"
          ),
          children: /* @__PURE__ */ jsx(
            "button",
            {
              type: "button",
              onClick: () => onToggle("filter"),
              className: cn(
                "flex size-full items-center justify-center rounded-md transition-all",
                toggles.filter ? "text-primary hover:bg-primary/10" : "text-foreground hover:bg-muted"
              ),
              children: /* @__PURE__ */ jsx(Settings2, { className: "size-4", strokeWidth: 1.5 })
            }
          )
        }
      ) }),
      /* @__PURE__ */ jsx(
        TooltipContent,
        {
          side: "bottom",
          className: "w-[360px] max-w-[90vw]",
          onMouseEnter: () => onContentMouseEnter("filter"),
          onMouseLeave: () => onContentMouseLeave("filter"),
          children: /* @__PURE__ */ jsxs("div", { className: "space-y-3", children: [
            /* @__PURE__ */ jsxs("div", { children: [
              /* @__PURE__ */ jsx("p", { className: "font-semibold", children: "Metadata Filtering" }),
              /* @__PURE__ */ jsx("p", { className: "text-muted-foreground mt-1 text-xs", children: "Filter by fields like source, status, or date before searching." })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
              /* @__PURE__ */ jsx("div", { className: "text-xs font-medium text-slate-400", children: "JSON:" }),
              /* @__PURE__ */ jsx(
                JsonFilterEditor,
                {
                  value: filterJson,
                  onChange: onFilterChange,
                  height: "160px"
                }
              )
            ] }),
            /* @__PURE__ */ jsx("div", { className: "border-border border-t pt-2", children: /* @__PURE__ */ jsx(
              "a",
              {
                href: "https://docs.airweave.ai/search#filtering-results",
                target: "_blank",
                rel: "noreferrer",
                className: "text-xs text-blue-400 hover:underline",
                children: "Docs"
              }
            ) })
          ] })
        }
      )
    ] }),
    /* @__PURE__ */ jsx(
      ToggleButton,
      {
        id: "queryInterpretation",
        icon: /* @__PURE__ */ jsx(Funnel, { className: "size-4", strokeWidth: 1.5 }),
        isActive: toggles.queryInterpretation,
        onClick: () => onToggle("queryInterpretation"),
        tooltip: {
          title: "Query Interpretation (Beta)",
          description: "Auto-extracts filters from natural language",
          docsUrl: "https://docs.airweave.ai/search#query-interpretation-beta"
        },
        openTooltip,
        onMouseEnter,
        onMouseLeave,
        onContentMouseEnter,
        onContentMouseLeave
      }
    ),
    /* @__PURE__ */ jsxs(Tooltip, { open: openTooltip === "recencyBias", children: [
      /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(
        "div",
        {
          onMouseEnter: () => onMouseEnter("recencyBias"),
          onMouseLeave: () => onMouseLeave("recencyBias"),
          className: cn(
            "h-7 w-8 overflow-hidden rounded-md border p-0",
            toggles.recencyBias ? "border-primary" : "border-border/50"
          ),
          children: /* @__PURE__ */ jsx(
            "button",
            {
              type: "button",
              onClick: () => onToggle("recencyBias"),
              className: cn(
                "flex size-full items-center justify-center rounded-md transition-all",
                toggles.recencyBias ? "text-primary hover:bg-primary/10" : "text-foreground hover:bg-muted"
              ),
              children: /* @__PURE__ */ jsx(ClockArrowUp, { className: "size-4", strokeWidth: 1.5 })
            }
          )
        }
      ) }),
      /* @__PURE__ */ jsxs(
        TooltipContent,
        {
          side: "bottom",
          className: "w-[240px]",
          onMouseEnter: () => onContentMouseEnter("recencyBias"),
          onMouseLeave: () => onContentMouseLeave("recencyBias"),
          children: [
            /* @__PURE__ */ jsx("p", { className: "font-semibold", children: "Recency Bias" }),
            /* @__PURE__ */ jsx("p", { className: "text-muted-foreground mb-2 text-xs", children: "Prioritize recent documents" }),
            /* @__PURE__ */ jsx("div", { className: "px-1.5 py-1", children: /* @__PURE__ */ jsx(
              RecencyBiasSlider,
              {
                value: recencyBiasValue,
                onChange: onRecencyBiasChange
              }
            ) }),
            /* @__PURE__ */ jsx("div", { className: "border-border mt-2 border-t pt-2", children: /* @__PURE__ */ jsx(
              "a",
              {
                href: "https://docs.airweave.ai/search#recency-bias",
                target: "_blank",
                rel: "noreferrer",
                className: "text-xs text-blue-400 hover:underline",
                children: "Docs"
              }
            ) })
          ]
        }
      )
    ] }),
    /* @__PURE__ */ jsx(
      ToggleButton,
      {
        id: "reRanking",
        icon: /* @__PURE__ */ jsx(ListStart, { className: "size-4", strokeWidth: 1.5 }),
        isActive: toggles.reRanking,
        onClick: () => onToggle("reRanking"),
        tooltip: {
          title: "AI Reranking",
          description: "LLM reorders results for better relevance",
          docsUrl: "https://docs.airweave.ai/search#ai-reranking"
        },
        openTooltip,
        onMouseEnter,
        onMouseLeave,
        onContentMouseEnter,
        onContentMouseLeave
      }
    ),
    /* @__PURE__ */ jsx(
      ToggleButton,
      {
        id: "answer",
        icon: /* @__PURE__ */ jsx(MessageSquare, { className: "size-4", strokeWidth: 1.5 }),
        isActive: toggles.answer,
        onClick: () => onToggle("answer"),
        tooltip: {
          title: "Generate Answer",
          description: "Returns an AI-written answer",
          docsUrl: "https://docs.airweave.ai/search#generate-ai-answers"
        },
        openTooltip,
        onMouseEnter,
        onMouseLeave,
        onContentMouseEnter,
        onContentMouseLeave
      }
    )
  ] });
}
const DEFAULT_TOGGLES = {
  queryExpansion: true,
  filter: false,
  queryInterpretation: false,
  recencyBias: false,
  reRanking: true,
  answer: true
};
function SearchBox({
  collectionId,
  onSearch,
  onSearchStart,
  onSearchEnd,
  onStreamEvent,
  onCancel,
  className,
  disabled,
  disabledReason
}) {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const { executeSearch, cancelSearch } = useSearchStream();
  const tooltipManager = useTooltipManager();
  const [query, setQuery] = useState("");
  const [searchMethod, setSearchMethod] = useState("hybrid");
  const [isSearching, setIsSearching] = useState(false);
  const [filterJson, setFilterJson] = useState("");
  const [isFilterValid, setIsFilterValid] = useState(true);
  const [recencyBiasValue, setRecencyBiasValue] = useState(0);
  const [toggles, setToggles] = useState(DEFAULT_TOGGLES);
  const [showCodeModal, setShowCodeModal] = useState(false);
  const [apiKey, setApiKey] = useState("YOUR_API_KEY");
  const [queriesAllowed, setQueriesAllowed] = useState(true);
  const [queriesCheckDetails, setQueriesCheckDetails] = useState(null);
  const [isCheckingUsage, setIsCheckingUsage] = useState(true);
  const [transientIssue, setTransientIssue] = useState(null);
  const hasQuery = query.trim().length > 0;
  const canRetrySearch = Boolean(transientIssue) && !isSearching;
  const isSearchDisabled = !queriesAllowed || isCheckingUsage || !!disabled;
  const checkQueriesAllowed = useCallback(async () => {
    if (!organization) return;
    try {
      setIsCheckingUsage(true);
      const token = await getAccessTokenSilently();
      const response = await fetch(
        `${API_BASE_URL}/usage/check-action?action=queries`,
        {
          headers: getAuthHeaders(token, organization.id)
        }
      );
      if (response.ok) {
        const data = await response.json();
        setQueriesAllowed(data.allowed);
        setQueriesCheckDetails(data);
      } else {
        setQueriesAllowed(true);
        setQueriesCheckDetails(null);
      }
    } catch {
      setQueriesAllowed(true);
      setQueriesCheckDetails(null);
    } finally {
      setIsCheckingUsage(false);
    }
  }, [organization, getAccessTokenSilently]);
  useEffect(() => {
    checkQueriesAllowed();
  }, [checkQueriesAllowed]);
  useEffect(() => {
    const fetchApiKey = async () => {
      if (!organization) return;
      try {
        const token = await getAccessTokenSilently();
        const response = await fetch(`${API_BASE_URL}/api-keys`, {
          headers: getAuthHeaders(token, organization.id)
        });
        if (response.ok) {
          const data = await response.json();
          if (Array.isArray(data) && data.length > 0 && data[0].decrypted_key) {
            setApiKey(data[0].decrypted_key);
          }
        }
      } catch (err) {
        console.error("Error fetching API key:", err);
      }
    };
    fetchApiKey();
  }, [organization, getAccessTokenSilently]);
  useKeyboardShortcut({
    key: "Escape",
    onKeyDown: () => setShowCodeModal(false),
    enabled: showCodeModal
  });
  useEffect(() => {
    if (showCodeModal) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [showCodeModal]);
  const handleCancelSearch = useCallback(() => {
    cancelSearch();
    onStreamEvent?.({ type: "cancelled" });
    onCancel?.();
    checkQueriesAllowed();
  }, [cancelSearch, onStreamEvent, onCancel, checkQueriesAllowed]);
  const handleSendQuery = useCallback(async () => {
    if (!hasQuery || !collectionId || isSearching || !organization || !queriesAllowed || isCheckingUsage)
      return;
    setTransientIssue(null);
    const currentResponseType = toggles.answer ? "completion" : "raw";
    setIsSearching(true);
    onSearchStart?.(currentResponseType);
    try {
      const token = await getAccessTokenSilently();
      let parsedFilter = null;
      if (toggles.filter && filterJson && isFilterValid) {
        try {
          parsedFilter = JSON.parse(filterJson);
        } catch {
          parsedFilter = null;
        }
      }
      const requestBody = {
        query,
        retrieval_strategy: searchMethod,
        expand_query: toggles.queryExpansion,
        interpret_filters: toggles.queryInterpretation,
        temporal_relevance: toggles.recencyBias ? recencyBiasValue : 0,
        rerank: toggles.reRanking,
        generate_answer: toggles.answer
      };
      if (parsedFilter) {
        requestBody.filter = parsedFilter;
      }
      await executeSearch({
        collectionId,
        query,
        requestBody,
        token,
        orgId: organization.id,
        onStreamEvent,
        onSuccess: (response, responseTime) => {
          onSearch(response, currentResponseType, responseTime);
        },
        onError: (error, responseTime, isTransient) => {
          if (isTransient) {
            setTransientIssue({ message: error.message });
            onSearch(
              {
                results: [],
                error: "Something went wrong, please try again.",
                errorIsTransient: true
              },
              currentResponseType,
              responseTime
            );
          } else {
            onSearch(
              { results: [], error: error.message, errorIsTransient: false },
              currentResponseType,
              responseTime
            );
          }
        }
      });
    } catch {
    } finally {
      setIsSearching(false);
      onSearchEnd?.();
      checkQueriesAllowed();
    }
  }, [
    hasQuery,
    collectionId,
    query,
    searchMethod,
    toggles,
    filterJson,
    isFilterValid,
    recencyBiasValue,
    isSearching,
    organization,
    queriesAllowed,
    isCheckingUsage,
    getAccessTokenSilently,
    executeSearch,
    onSearch,
    onSearchStart,
    onSearchEnd,
    onStreamEvent,
    checkQueriesAllowed
  ]);
  const handleToggle = useCallback(
    (name) => {
      if (name === "filter") {
        setToggles((prev) => {
          const newFilterState = !prev.filter;
          if (newFilterState) {
            tooltipManager.forceOpen("filter");
          }
          return { ...prev, filter: newFilterState };
        });
      } else if (name === "recencyBias") {
        setToggles((prev) => {
          const newState = !prev.recencyBias;
          if (newState) {
            tooltipManager.forceOpen("recencyBias");
          }
          return { ...prev, recencyBias: newState };
        });
      } else {
        setToggles((prev) => ({ ...prev, [name]: !prev[name] }));
      }
    },
    [tooltipManager]
  );
  const handleRecencyBiasChange = useCallback((value) => {
    setRecencyBiasValue(value);
    setToggles((prev) => ({ ...prev, recencyBias: value > 0 }));
  }, []);
  const handleFilterChange = useCallback((value, isValid) => {
    setFilterJson(value);
    setIsFilterValid(isValid);
  }, []);
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx("div", { className: cn("w-full", className), children: /* @__PURE__ */ jsxs("div", { className: "bg-card overflow-hidden rounded-lg border", children: [
      /* @__PURE__ */ jsxs("div", { className: "relative px-2 pt-2 pb-1", children: [
        /* @__PURE__ */ jsx(CodeButton, { onClick: () => setShowCodeModal(true) }),
        /* @__PURE__ */ jsx(
          SearchInput,
          {
            value: query,
            onChange: setQuery,
            onSubmit: handleSendQuery,
            isDisabled: isSearchDisabled,
            isSearching,
            usageLimit: isSearchDisabled ? {
              isChecking: isCheckingUsage,
              isAllowed: queriesAllowed && !disabled,
              reason: disabled ? disabledReason : queriesCheckDetails?.reason
            } : void 0
          }
        )
      ] }),
      /* @__PURE__ */ jsx("div", { className: "flex items-center justify-between px-2 pb-2", children: /* @__PURE__ */ jsxs(TooltipProvider, { delayDuration: 0, children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-1.5", children: [
          /* @__PURE__ */ jsx(
            SearchMethodSelector,
            {
              value: searchMethod,
              onChange: setSearchMethod,
              openTooltip: tooltipManager.openTooltip,
              onMouseEnter: tooltipManager.handleMouseEnter,
              onMouseLeave: tooltipManager.handleMouseLeave,
              onContentMouseEnter: tooltipManager.handleContentMouseEnter,
              onContentMouseLeave: tooltipManager.handleContentMouseLeave
            }
          ),
          /* @__PURE__ */ jsx(
            SearchTogglesPanel,
            {
              toggles,
              onToggle: handleToggle,
              filterJson,
              onFilterChange: handleFilterChange,
              recencyBiasValue,
              onRecencyBiasChange: handleRecencyBiasChange,
              openTooltip: tooltipManager.openTooltip,
              onMouseEnter: tooltipManager.handleMouseEnter,
              onMouseLeave: tooltipManager.handleMouseLeave,
              onContentMouseEnter: tooltipManager.handleContentMouseEnter,
              onContentMouseLeave: tooltipManager.handleContentMouseLeave
            }
          )
        ] }),
        /* @__PURE__ */ jsx(
          SearchSubmitButton,
          {
            isSearching,
            hasQuery,
            queriesAllowed,
            isCheckingUsage,
            canRetry: canRetrySearch,
            retryMessage: transientIssue?.message,
            onSubmit: handleSendQuery,
            onCancel: handleCancelSearch,
            onRetry: () => {
              setTransientIssue(null);
              handleSendQuery();
            }
          }
        )
      ] }) })
    ] }) }),
    showCodeModal && collectionId && /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx(
        "div",
        {
          className: "fixed inset-0 z-40 bg-black/60 backdrop-blur-sm",
          onClick: () => setShowCodeModal(false)
        }
      ),
      /* @__PURE__ */ jsx("div", { className: "pointer-events-none fixed inset-0 z-50 flex items-center justify-center p-8", children: /* @__PURE__ */ jsxs(
        "div",
        {
          className: "pointer-events-auto relative w-full max-w-4xl",
          onClick: (e) => e.stopPropagation(),
          children: [
            /* @__PURE__ */ jsx(
              "button",
              {
                onClick: () => setShowCodeModal(false),
                className: "bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground absolute top-2 right-2 z-10 flex size-8 items-center justify-center rounded-md transition-colors",
                title: "Close (Esc)",
                children: /* @__PURE__ */ jsx(X, { className: "size-4" })
              }
            ),
            /* @__PURE__ */ jsx(
              ApiIntegrationModal,
              {
                collectionReadableId: collectionId,
                query: query || "Ask a question about your data",
                searchConfig: {
                  search_method: searchMethod,
                  expansion_strategy: toggles.queryExpansion ? "auto" : "no_expansion",
                  enable_query_interpretation: toggles.queryInterpretation,
                  recency_bias: toggles.recencyBias ? recencyBiasValue : 0,
                  enable_reranking: toggles.reRanking,
                  response_type: toggles.answer ? "completion" : "raw"
                },
                filter: toggles.filter ? filterJson : null,
                apiKey
              }
            )
          ]
        }
      ) })
    ] })
  ] });
}
function useLocalStorageState(key, defaultValue) {
  const [state, setState] = useState(() => {
    if (typeof window === "undefined") {
      return defaultValue;
    }
    try {
      const stored = localStorage.getItem(key);
      if (stored === null) {
        return defaultValue;
      }
      if (typeof defaultValue === "boolean") {
        return stored === "true";
      }
      if (typeof defaultValue === "number") {
        const num = parseFloat(stored);
        return isNaN(num) ? defaultValue : num;
      }
      if (typeof defaultValue === "string") {
        return stored;
      }
      return JSON.parse(stored);
    } catch {
      return defaultValue;
    }
  });
  const setStateWithStorage = useCallback(
    (value) => {
      setState((prev) => {
        const nextValue = typeof value === "function" ? value(prev) : value;
        try {
          if (typeof nextValue === "object") {
            localStorage.setItem(key, JSON.stringify(nextValue));
          } else {
            localStorage.setItem(key, String(nextValue));
          }
        } catch {
        }
        return nextValue;
      });
    },
    [key]
  );
  return [state, setStateWithStorage];
}
function parseInlineText(text, onCitationClick, keyBase) {
  const elements = [];
  const combinedRegex = /(\[\[(\d+)\]\])|(`([^`]+)`)|(\*\*([^*]+)\*\*)|(\[([^\]]+)\]\(([^)]+)\))/g;
  let lastIndex = 0;
  let match;
  let elementKey = 0;
  while ((match = combinedRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      elements.push(text.substring(lastIndex, match.index));
    }
    if (match[1]) {
      const citationNum = parseInt(match[2], 10);
      elements.push(
        /* @__PURE__ */ jsx(
          "button",
          {
            onClick: () => onCitationClick(citationNum - 1),
            className: "mx-0.5 inline-flex size-5 items-center justify-center rounded bg-blue-500/20 text-xs font-medium text-blue-400 transition-colors hover:bg-blue-500/30",
            title: `Jump to source ${citationNum}`,
            children: citationNum
          },
          `cite-${keyBase}-${elementKey++}`
        )
      );
    } else if (match[3]) {
      elements.push(
        /* @__PURE__ */ jsx(
          "code",
          {
            className: "rounded bg-slate-800 px-1.5 py-0.5 text-sm text-slate-200",
            children: match[4]
          },
          `code-${keyBase}-${elementKey++}`
        )
      );
    } else if (match[5]) {
      elements.push(
        /* @__PURE__ */ jsx("strong", { children: match[6] }, `bold-${keyBase}-${elementKey++}`)
      );
    } else if (match[7]) {
      elements.push(
        /* @__PURE__ */ jsx(
          "a",
          {
            href: match[9],
            target: "_blank",
            rel: "noopener noreferrer",
            className: "text-blue-400 underline hover:text-blue-300",
            children: match[8]
          },
          `link-${keyBase}-${elementKey++}`
        )
      );
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    elements.push(text.substring(lastIndex));
  }
  return elements;
}
function parseInlineContent(text, onCitationClick, keyBase) {
  const elements = [];
  const paragraphs = text.split(/\n\n+/);
  paragraphs.forEach((paragraph, pIdx) => {
    if (!paragraph.trim()) return;
    const lines = paragraph.split("\n");
    const listItems = lines.filter((line) => /^[-*\d.]\s/.test(line.trim()));
    if (listItems.length > 0 && listItems.length === lines.length) {
      const listElements = lines.map((line, lineIdx) => {
        const cleanLine = line.replace(/^[-*\d.]\s+/, "");
        return /* @__PURE__ */ jsx("li", { children: parseInlineText(
          cleanLine,
          onCitationClick,
          `${keyBase}-${pIdx}-${lineIdx}`
        ) }, `li-${keyBase}-${pIdx}-${lineIdx}`);
      });
      elements.push(
        /* @__PURE__ */ jsx(
          "ul",
          {
            className: "my-2 ml-4 list-disc space-y-1",
            children: listElements
          },
          `ul-${keyBase}-${pIdx}`
        )
      );
    } else {
      elements.push(
        /* @__PURE__ */ jsx("p", { className: "my-2", children: parseInlineText(
          paragraph.replace(/\n/g, " "),
          onCitationClick,
          `${keyBase}-${pIdx}`
        ) }, `p-${keyBase}-${pIdx}`)
      );
    }
  });
  return elements;
}
function parseMarkdownContent(content, onCitationClick) {
  const elements = [];
  const codeBlockRegex = /```(\w*)\n?([\s\S]*?)```/g;
  let match;
  let lastEnd = 0;
  while ((match = codeBlockRegex.exec(content)) !== null) {
    if (match.index > lastEnd) {
      const textBefore = content.substring(lastEnd, match.index);
      elements.push(
        ...parseInlineContent(textBefore, onCitationClick, elements.length)
      );
    }
    const language = match[1] || "text";
    const code = match[2];
    elements.push(
      /* @__PURE__ */ jsx(
        "pre",
        {
          className: "my-3 overflow-x-auto rounded-lg bg-slate-900 p-4",
          children: /* @__PURE__ */ jsx("code", { className: `language-${language} text-sm text-slate-200`, children: code.trim() })
        },
        `code-${elements.length}`
      )
    );
    lastEnd = match.index + match[0].length;
  }
  if (lastEnd < content.length) {
    const remainingText = content.substring(lastEnd);
    elements.push(
      ...parseInlineContent(remainingText, onCitationClick, elements.length)
    );
  }
  return elements;
}
function formatResponseTime(ms) {
  if (ms < 1e3) {
    return `${ms}ms`;
  }
  return `${(ms / 1e3).toFixed(2)}s`;
}
function useAutoScroll(deps, options = {}) {
  const { enabled = true } = options;
  const scrollRef = useRef(null);
  useEffect(() => {
    if (!enabled || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [enabled, ...deps]);
  return scrollRef;
}
const EVENT_TYPE_LABELS = {
  query_expansion_started: "Query Expansion",
  query_expansion_done: "Query Expansion",
  filter_interpretation_started: "Filter Interpretation",
  filter_interpretation_done: "Filter Interpretation",
  retrieval_started: "Retrieval",
  retrieval_done: "Retrieval",
  reranking_started: "Reranking",
  reranking_done: "Reranking",
  completion_started: "Generating Answer",
  completion_chunk: "Generating Answer",
  completion_done: "Answer Complete",
  results: "Results",
  done: "Complete",
  error: "Error"
};
function groupEvents(events) {
  const groups = [];
  const groupMap = /* @__PURE__ */ new Map();
  for (const event of events) {
    const eventType = event.type;
    let groupKey = eventType;
    let status = "completed";
    if (eventType.endsWith("_started")) {
      groupKey = eventType.replace("_started", "");
      status = "in_progress";
    } else if (eventType.endsWith("_done")) {
      groupKey = eventType.replace("_done", "");
      status = "completed";
    } else if (eventType === "completion_chunk") {
      groupKey = "completion";
      status = "in_progress";
    } else if (eventType === "error") {
      status = "error";
    }
    const label = EVENT_TYPE_LABELS[eventType] || eventType;
    let group = groupMap.get(groupKey);
    if (!group) {
      group = {
        id: groupKey,
        label,
        events: [],
        status: "pending"
      };
      groupMap.set(groupKey, group);
      groups.push(group);
    }
    group.events.push(event);
    group.status = status;
    group.label = label;
    const eventData = event;
    if (eventData.expanded_queries) {
      group.output = { expanded_queries: eventData.expanded_queries };
    }
    if (eventData.interpreted_filter) {
      group.output = { interpreted_filter: eventData.interpreted_filter };
    }
    if (eventData.results) {
      group.output = { result_count: eventData.results.length };
    }
    if (eventData.duration_ms) {
      group.duration = eventData.duration_ms;
    }
  }
  return groups;
}
function StatusIndicator({ status }) {
  switch (status) {
    case "pending":
      return /* @__PURE__ */ jsx("div", { className: "size-2 rounded-full bg-slate-500" });
    case "in_progress":
      return /* @__PURE__ */ jsx(LoaderCircle, { className: "size-3 animate-spin text-blue-500" });
    case "completed":
      return /* @__PURE__ */ jsx("div", { className: "flex size-4 items-center justify-center rounded-full bg-green-500/20", children: /* @__PURE__ */ jsx(Check, { className: "size-2.5 text-green-500" }) });
    case "error":
      return /* @__PURE__ */ jsx("div", { className: "size-2 rounded-full bg-red-500" });
    default:
      return null;
  }
}
function EventGroupRow({
  group,
  isExpanded,
  onToggle
}) {
  const output = group.output;
  const hasOutput = output && Object.keys(output).length > 0;
  return /* @__PURE__ */ jsxs("div", { className: "border-b border-slate-800 last:border-b-0", children: [
    /* @__PURE__ */ jsxs(
      "button",
      {
        onClick: hasOutput ? onToggle : void 0,
        className: cn(
          "flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors",
          hasOutput && "cursor-pointer hover:bg-slate-800/50"
        ),
        disabled: !hasOutput,
        children: [
          /* @__PURE__ */ jsx("div", { className: "w-4", children: hasOutput && (isExpanded ? /* @__PURE__ */ jsx(ChevronDown, { className: "size-3.5 text-slate-400" }) : /* @__PURE__ */ jsx(ChevronRight, { className: "size-3.5 text-slate-400" })) }),
          /* @__PURE__ */ jsx(StatusIndicator, { status: group.status }),
          /* @__PURE__ */ jsx(
            "span",
            {
              className: cn(
                "flex-1 text-sm",
                group.status === "error" ? "text-red-400" : "text-slate-200"
              ),
              children: group.label
            }
          ),
          group.duration !== void 0 && /* @__PURE__ */ jsxs("span", { className: "text-xs text-slate-500", children: [
            group.duration,
            "ms"
          ] })
        ]
      }
    ),
    isExpanded && hasOutput && /* @__PURE__ */ jsx("div", { className: "border-t border-slate-800 bg-slate-950 px-4 py-3", children: /* @__PURE__ */ jsx("pre", { className: "overflow-x-auto text-xs text-slate-400", children: JSON.stringify(output, null, 2) }) })
  ] });
}
function SearchTrace({
  events,
  isSearching = false,
  className
}) {
  const [expandedGroups, setExpandedGroups] = useState(/* @__PURE__ */ new Set());
  const [copied, setCopied] = useState(false);
  const scrollRef = useAutoScroll([events], { enabled: isSearching });
  const eventGroups = useMemo(() => groupEvents(events), [events]);
  const toggleGroup = useCallback((groupId) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) {
        next.delete(groupId);
      } else {
        next.add(groupId);
      }
      return next;
    });
  }, []);
  const handleCopyTrace = useCallback(async () => {
    const traceData = {
      timestamp: (/* @__PURE__ */ new Date()).toISOString(),
      events
    };
    await navigator.clipboard.writeText(JSON.stringify(traceData, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2e3);
  }, [events]);
  if (events.length === 0 && !isSearching) {
    return null;
  }
  return /* @__PURE__ */ jsxs("div", { className: cn("overflow-hidden", className), children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between border-b border-slate-800 bg-slate-900 px-4 py-2", children: [
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ jsx("span", { className: "text-sm font-medium text-slate-200", children: "Search Trace" }),
        isSearching && /* @__PURE__ */ jsx(LoaderCircle, { className: "size-3 animate-spin text-blue-500" })
      ] }),
      /* @__PURE__ */ jsx(
        Button,
        {
          variant: "ghost",
          size: "sm",
          onClick: handleCopyTrace,
          className: "size-7 p-0 text-slate-400 hover:text-slate-200",
          title: "Copy trace",
          children: copied ? /* @__PURE__ */ jsx(Check, { className: "size-3.5 text-green-500" }) : /* @__PURE__ */ jsx(Copy, { className: "size-3.5" })
        }
      )
    ] }),
    /* @__PURE__ */ jsxs(
      "div",
      {
        ref: scrollRef,
        className: "max-h-[400px] overflow-y-auto bg-slate-900/50",
        children: [
          eventGroups.map((group) => /* @__PURE__ */ jsx(
            EventGroupRow,
            {
              group,
              isExpanded: expandedGroups.has(group.id),
              onToggle: () => toggleGroup(group.id)
            },
            group.id
          )),
          isSearching && events.length === 0 && /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3 px-4 py-3", children: [
            /* @__PURE__ */ jsx(LoaderCircle, { className: "size-4 animate-spin text-blue-500" }),
            /* @__PURE__ */ jsx("span", { className: "text-sm text-slate-400", children: "Starting search..." })
          ] })
        ]
      }
    )
  ] });
}
const STORAGE_KEYS = {
  EXPANDED: "searchResponse-expanded",
  ACTIVE_TAB: "searchResponse-activeTab"
};
function SearchResponse({
  searchResponse,
  isSearching,
  responseType = "raw",
  events = [],
  className
}) {
  const [copiedCompletion, setCopiedCompletion] = useState(false);
  const [copiedRawJson, setCopiedRawJson] = useState(false);
  const defaultTab = responseType === "completion" ? "answer" : "entities";
  const [activeTab, setActiveTab] = useLocalStorageState(
    STORAGE_KEYS.ACTIVE_TAB,
    defaultTab
  );
  const [isExpanded, setIsExpanded] = useLocalStorageState(
    STORAGE_KEYS.EXPANDED,
    true
  );
  const INITIAL_RESULTS_LIMIT = 25;
  const LOAD_MORE_INCREMENT = 25;
  const [visibleResultsCount, setVisibleResultsCount] = useState(
    INITIAL_RESULTS_LIMIT
  );
  const RAW_JSON_LINE_LIMIT = 500;
  const [showFullRawJson, setShowFullRawJson] = useState(false);
  const entityRefs = useRef(/* @__PURE__ */ new Map());
  const completion = searchResponse?.completion || "";
  const results = useMemo(
    () => searchResponse?.results || [],
    [searchResponse?.results]
  );
  const responseTime = searchResponse?.responseTime;
  const hasError = Boolean(searchResponse?.error);
  const isTransientError = Boolean(searchResponse?.errorIsTransient);
  const errorDisplayMessage = isTransientError ? "Something went wrong, please try again." : searchResponse?.error;
  const scrollToEntity = useCallback(
    (index) => {
      const ref = entityRefs.current.get(index);
      if (ref) {
        ref.scrollIntoView({ behavior: "smooth", block: "center" });
        ref.classList.add("ring-2", "ring-blue-500");
        setTimeout(() => {
          ref.classList.remove("ring-2", "ring-blue-500");
        }, 1500);
      }
      setActiveTab("entities");
    },
    [setActiveTab]
  );
  const handleCopyCompletion = useCallback(async () => {
    if (completion) {
      await navigator.clipboard.writeText(completion);
      setCopiedCompletion(true);
      setTimeout(() => setCopiedCompletion(false), 2e3);
    }
  }, [completion]);
  const handleCopyRawJson = useCallback(async () => {
    if (searchResponse) {
      await navigator.clipboard.writeText(
        JSON.stringify(searchResponse, null, 2)
      );
      setCopiedRawJson(true);
      setTimeout(() => setCopiedRawJson(false), 2e3);
    }
  }, [searchResponse]);
  const rawJsonContent = useMemo(() => {
    if (!searchResponse) return "";
    const fullJson = JSON.stringify(searchResponse, null, 2);
    const lines = fullJson.split("\n");
    if (!showFullRawJson && lines.length > RAW_JSON_LINE_LIMIT) {
      return lines.slice(0, RAW_JSON_LINE_LIMIT).join("\n") + "\n// ...";
    }
    return fullJson;
  }, [searchResponse, showFullRawJson]);
  const rawJsonLineCount = useMemo(() => {
    if (!searchResponse) return 0;
    return JSON.stringify(searchResponse, null, 2).split("\n").length;
  }, [searchResponse]);
  const visibleResults = useMemo(
    () => results.slice(0, visibleResultsCount),
    [results, visibleResultsCount]
  );
  const hasMoreResults = results.length > visibleResultsCount;
  const hasTrace = events.length > 0;
  const renderedCompletion = useMemo(() => {
    if (!completion) return null;
    return parseMarkdownContent(completion, scrollToEntity);
  }, [completion, scrollToEntity]);
  if (!searchResponse && !isSearching) {
    return null;
  }
  if (isSearching && !searchResponse) {
    return /* @__PURE__ */ jsx("div", { className: cn("bg-card mt-4 rounded-lg border p-6", className), children: /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-center gap-2", children: [
      /* @__PURE__ */ jsx(LoaderCircle, { className: "size-4 animate-spin" }),
      /* @__PURE__ */ jsx("span", { className: "text-muted-foreground text-sm", children: "Searching..." })
    ] }) });
  }
  if (hasError) {
    return /* @__PURE__ */ jsx(
      "div",
      {
        className: cn(
          "border-destructive/50 bg-destructive/10 mt-4 rounded-lg border p-6",
          className
        ),
        children: /* @__PURE__ */ jsx("p", { className: "text-destructive text-sm", children: errorDisplayMessage })
      }
    );
  }
  if (results.length === 0 && !completion) {
    return /* @__PURE__ */ jsx(
      EmptyState,
      {
        icon: /* @__PURE__ */ jsx(SearchX, {}),
        title: "No results found",
        description: "Try adjusting your search query",
        className: cn("bg-card mt-4 rounded-lg border", className)
      }
    );
  }
  return /* @__PURE__ */ jsxs("div", { className: cn("mt-4 space-y-4", className), children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between", children: [
      /* @__PURE__ */ jsxs("div", { className: "flex gap-2", children: [
        hasTrace && /* @__PURE__ */ jsx(
          Button,
          {
            variant: activeTab === "trace" ? "default" : "outline",
            size: "sm",
            onClick: () => setActiveTab("trace"),
            children: "Trace"
          }
        ),
        completion && /* @__PURE__ */ jsx(
          Button,
          {
            variant: activeTab === "answer" ? "default" : "outline",
            size: "sm",
            onClick: () => setActiveTab("answer"),
            children: "Answer"
          }
        ),
        /* @__PURE__ */ jsxs(
          Button,
          {
            variant: activeTab === "entities" ? "default" : "outline",
            size: "sm",
            onClick: () => setActiveTab("entities"),
            children: [
              "Results (",
              results.length,
              ")"
            ]
          }
        ),
        /* @__PURE__ */ jsx(
          Button,
          {
            variant: activeTab === "raw" ? "default" : "outline",
            size: "sm",
            onClick: () => setActiveTab("raw"),
            children: "Raw"
          }
        )
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
        responseTime && /* @__PURE__ */ jsx("span", { className: "text-muted-foreground text-xs", children: formatResponseTime(responseTime) }),
        /* @__PURE__ */ jsx(
          Button,
          {
            variant: "ghost",
            size: "sm",
            onClick: () => setIsExpanded(!isExpanded),
            className: "size-8 p-0",
            children: isExpanded ? /* @__PURE__ */ jsx(ChevronUp, { className: "size-4" }) : /* @__PURE__ */ jsx(ChevronDown, { className: "size-4" })
          }
        )
      ] })
    ] }),
    isExpanded && /* @__PURE__ */ jsxs(Fragment, { children: [
      activeTab === "trace" && hasTrace && /* @__PURE__ */ jsx(
        SearchTrace,
        {
          events,
          isSearching,
          className: "bg-card rounded-lg border"
        }
      ),
      activeTab === "answer" && completion && /* @__PURE__ */ jsxs("div", { className: "bg-card rounded-lg border p-4", children: [
        /* @__PURE__ */ jsxs("div", { className: "mb-3 flex items-center justify-between", children: [
          /* @__PURE__ */ jsx("h3", { className: "text-sm font-semibold", children: "AI-Generated Answer" }),
          /* @__PURE__ */ jsx(
            Button,
            {
              variant: "ghost",
              size: "sm",
              onClick: handleCopyCompletion,
              className: "size-8 p-0",
              children: copiedCompletion ? /* @__PURE__ */ jsx(Check, { className: "size-4 text-green-500" }) : /* @__PURE__ */ jsx(Copy, { className: "size-4" })
            }
          )
        ] }),
        /* @__PURE__ */ jsx("div", { className: "prose prose-sm dark:prose-invert max-w-none text-sm leading-relaxed", children: renderedCompletion })
      ] }),
      activeTab === "entities" && results.length > 0 && /* @__PURE__ */ jsxs("div", { className: "space-y-3", children: [
        /* @__PURE__ */ jsx("div", { className: "flex items-center justify-between", children: /* @__PURE__ */ jsxs("h3", { className: "text-sm font-semibold", children: [
          results.length,
          " Result",
          results.length !== 1 ? "s" : ""
        ] }) }),
        /* @__PURE__ */ jsx("div", { className: "space-y-3", children: visibleResults.map((result, index) => /* @__PURE__ */ jsx(
          "div",
          {
            ref: (el) => {
              if (el) {
                entityRefs.current.set(index, el);
              }
            },
            "data-entity-index": index,
            className: "transition-all duration-200",
            children: /* @__PURE__ */ jsx(EntityResultCard, { result, index })
          },
          result.id || result.entity_id || index
        )) }),
        hasMoreResults && /* @__PURE__ */ jsx("div", { className: "flex justify-center pt-2", children: /* @__PURE__ */ jsxs(
          Button,
          {
            variant: "outline",
            size: "sm",
            onClick: () => setVisibleResultsCount(
              (prev) => prev + LOAD_MORE_INCREMENT
            ),
            children: [
              "Load",
              " ",
              Math.min(
                LOAD_MORE_INCREMENT,
                results.length - visibleResultsCount
              ),
              " ",
              "More"
            ]
          }
        ) })
      ] }),
      activeTab === "raw" && searchResponse && /* @__PURE__ */ jsxs("div", { className: "bg-card rounded-lg border", children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between border-b px-4 py-2", children: [
          /* @__PURE__ */ jsxs("span", { className: "text-muted-foreground text-xs", children: [
            rawJsonLineCount,
            " lines"
          ] }),
          /* @__PURE__ */ jsx(
            Button,
            {
              variant: "ghost",
              size: "sm",
              onClick: handleCopyRawJson,
              className: "size-8 p-0",
              children: copiedRawJson ? /* @__PURE__ */ jsx(Check, { className: "size-4 text-green-500" }) : /* @__PURE__ */ jsx(Copy, { className: "size-4" })
            }
          )
        ] }),
        /* @__PURE__ */ jsx("div", { className: "max-h-[500px] overflow-auto bg-slate-900 p-4", children: /* @__PURE__ */ jsx("pre", { className: "text-xs text-slate-300", children: /* @__PURE__ */ jsx("code", { children: rawJsonContent }) }) }),
        rawJsonLineCount > RAW_JSON_LINE_LIMIT && !showFullRawJson && /* @__PURE__ */ jsx("div", { className: "border-t px-4 py-2", children: /* @__PURE__ */ jsxs(
          Button,
          {
            variant: "ghost",
            size: "sm",
            onClick: () => setShowFullRawJson(true),
            className: "text-xs",
            children: [
              "Show all ",
              rawJsonLineCount,
              " lines"
            ]
          }
        ) })
      ] })
    ] }),
    isSearching && /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-center gap-2 py-2", children: [
      /* @__PURE__ */ jsx(LoaderCircle, { className: "size-4 animate-spin" }),
      /* @__PURE__ */ jsx("span", { className: "text-muted-foreground text-xs", children: "Updating results..." })
    ] })
  ] });
}
function Search({
  collectionReadableId,
  className,
  disabled,
  disabledReason
}) {
  const [searchResponse, setSearchResponse] = useState(null);
  const [searchResponseType, setSearchResponseType] = useState("raw");
  const [showResponsePanel, setShowResponsePanel] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [liveResults, setLiveResults] = useState([]);
  const [events, setEvents] = useState([]);
  const handleSearchResult = useCallback(
    (response, responseType, _responseTimeMs) => {
      setSearchResponse(response);
      setSearchResponseType(responseType);
    },
    []
  );
  const handleSearchStart = useCallback(
    (responseType) => {
      if (!showResponsePanel) setShowResponsePanel(true);
      setIsSearching(true);
      setSearchResponse(null);
      setSearchResponseType(responseType);
      setLiveResults([]);
      setEvents([]);
    },
    [showResponsePanel]
  );
  const handleSearchEnd = useCallback(() => {
    setIsSearching(false);
  }, []);
  const handleStreamEvent = useCallback((event) => {
    setEvents((prev) => [...prev, event]);
    if (event.type === "results") {
      setLiveResults(event.results);
    }
  }, []);
  const handleCancel = useCallback(() => {
    setEvents((prev) => [...prev, { type: "cancelled" }]);
  }, []);
  return /* @__PURE__ */ jsxs("div", { className: cn("w-full", className), children: [
    /* @__PURE__ */ jsx("div", { children: /* @__PURE__ */ jsx(
      SearchBox,
      {
        collectionId: collectionReadableId,
        onSearch: handleSearchResult,
        onSearchStart: handleSearchStart,
        onSearchEnd: handleSearchEnd,
        onStreamEvent: handleStreamEvent,
        onCancel: handleCancel,
        disabled,
        disabledReason
      }
    ) }),
    showResponsePanel && /* @__PURE__ */ jsx("div", { children: /* @__PURE__ */ jsx(
      SearchResponse,
      {
        searchResponse: isSearching ? { results: liveResults } : searchResponse,
        isSearching,
        responseType: searchResponseType,
        events
      }
    ) })
  ] });
}
function CollectionDetailPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    getAccessTokenSilently
  } = useAuth0();
  const {
    organization,
    getOrgSlug
  } = useOrg();
  const queryClient = useQueryClient();
  const params = Route.useParams();
  const collectionId = params.collectionId;
  if (!organization) {
    throw new Error("Organization context is required but not available");
  }
  const orgId = organization.id;
  const orgSlug = getOrgSlug(organization);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showAddSourceDialog, setShowAddSourceDialog] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState(null);
  const processedNavState = useRef(false);
  const openAddSource = useAddSourceStore((s) => s.open);
  const {
    data: collection,
    isLoading: isLoadingCollection,
    error: collectionError,
    refetch: refetchCollection
  } = useQuery({
    queryKey: queryKeys.collections.detail(orgId, collectionId),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchCollection(token, orgId, collectionId);
    }
  });
  const {
    data: sourceConnections = [],
    error: connectionsError,
    refetch: refetchConnections
  } = useQuery({
    queryKey: queryKeys.sourceConnections.list(orgId, collectionId),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSourceConnections(token, orgId, collectionId);
    },
    enabled: !!collection
  });
  const selectedConnection = useMemo(() => {
    if (!sourceConnections.length) return null;
    if (selectedConnectionId) {
      const found = sourceConnections.find((c) => c.id === selectedConnectionId);
      if (found) return found;
    }
    return sourceConnections[0];
  }, [sourceConnections, selectedConnectionId]);
  useEffect(() => {
    if (sourceConnections.length > 0 && !selectedConnectionId) {
      setSelectedConnectionId(sourceConnections[0].id);
    }
  }, [sourceConnections, selectedConnectionId]);
  useEffect(() => {
    if (processedNavState.current || !collection) return;
    const navState = location.state;
    if (navState?.addSource) {
      processedNavState.current = true;
      openAddSource(collection.readable_id, collection.name, navState.addSource);
      setShowAddSourceDialog(true);
      navigate({
        to: location.pathname,
        replace: true
      });
    }
  }, [collection, location.state, location.pathname, navigate, openAddSource]);
  const deleteMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return deleteCollection(token, orgId, collectionId);
    },
    onSuccess: () => {
      toast.success("Collection deleted successfully");
      queryClient.invalidateQueries({
        queryKey: queryKeys.collections.all(orgId)
      });
      navigate({
        to: `/${orgSlug}/collections`
      });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Failed to delete collection");
    }
  });
  usePageHeader({
    title: collection?.name || "Loading...",
    description: collection?.readable_id || ""
  });
  useRightSidebarContent({
    docs: /* @__PURE__ */ jsx(CollectionDetailDocs, {}),
    code: /* @__PURE__ */ jsx(CollectionDetailCode, { collectionId }),
    help: /* @__PURE__ */ jsx(CollectionDetailHelp, {})
  });
  const handleReload = useCallback(() => {
    refetchCollection();
    refetchConnections();
  }, [refetchCollection, refetchConnections]);
  const handleAddSource = useCallback(() => {
    if (collection) {
      openAddSource(collection.readable_id, collection.name);
      setShowAddSourceDialog(true);
    }
  }, [collection, openAddSource]);
  if (isLoadingCollection) {
    return /* @__PURE__ */ jsx("div", { className: "flex h-full items-center justify-center p-6", children: /* @__PURE__ */ jsx(LoadingState, {}) });
  }
  if (collectionError || connectionsError) {
    return /* @__PURE__ */ jsx("div", { className: "p-6", children: /* @__PURE__ */ jsx(ErrorState, { error: collectionError instanceof Error ? collectionError : connectionsError instanceof Error ? connectionsError : "Failed to load collection" }) });
  }
  if (!collection) {
    return /* @__PURE__ */ jsx("div", { className: "p-6", children: /* @__PURE__ */ jsx(ErrorState, { error: "Collection not found" }) });
  }
  return /* @__PURE__ */ jsxs("div", { className: "container mx-auto flex max-w-[1000px] flex-col items-center py-6", children: [
    /* @__PURE__ */ jsx(CollectionHeader, { collection, sourceConnections, onReload: handleReload, onDelete: () => setShowDeleteDialog(true) }),
    /* @__PURE__ */ jsx("div", { className: "mt-10 w-full", children: /* @__PURE__ */ jsx(Search, { collectionReadableId: collection.readable_id, disabled: sourceConnections.length === 0, disabledReason: "no_sources" }) }),
    /* @__PURE__ */ jsx("div", { className: "mt-8 w-full", children: /* @__PURE__ */ jsx(SourceConnectionsList, { sourceConnections, selectedConnectionId, onSelectConnection: setSelectedConnectionId, onAddSource: handleAddSource }) }),
    selectedConnection && /* @__PURE__ */ jsx("div", { className: "mt-4 w-full", children: /* @__PURE__ */ jsx(SourceConnectionStateView, { sourceConnection: selectedConnection, onConnectionDeleted: () => {
      setSelectedConnectionId(null);
      refetchConnections();
    }, onConnectionUpdated: refetchConnections }, selectedConnection.id) }),
    /* @__PURE__ */ jsx(DeleteCollectionDialog, { open: showDeleteDialog, onOpenChange: setShowDeleteDialog, onConfirm: () => deleteMutation.mutate(), collectionReadableId: collection.readable_id, isDeleting: deleteMutation.isPending }),
    /* @__PURE__ */ jsx(AddSourceDialog, { open: showAddSourceDialog, onOpenChange: (open) => {
      setShowAddSourceDialog(open);
      if (!open) {
        refetchConnections();
      }
    } })
  ] });
}
export {
  CollectionDetailPage as component
};
