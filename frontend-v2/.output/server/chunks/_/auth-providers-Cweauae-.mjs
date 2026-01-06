import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { E as EmptyState } from "./empty-state-BldPO3ai.mjs";
import { E as ErrorState, C as Copy, A as AlertDialog, b as AlertDialogContent, c as AlertDialogHeader, d as AlertDialogTitle, e as AlertDialogDescription, i as CircleAlert, f as AlertDialogFooter, g as AlertDialogCancel, h as AlertDialogAction } from "./error-state-BYmPP-hR.mjs";
import { L as LoadingState } from "./loading-state-CJE8ekwd.mjs";
import { u as useAuth0, a9 as usePageHeader, aa as useRightSidebarContent, q as queryKeys, ad as ShieldCheck, a as cn, B as Button, h as Check, P as Plus, D as Dialog, k as DialogContent, l as DialogHeader, m as DialogTitle, n as DialogDescription, L as LoaderCircle, Y as DialogFooter, ae as TriangleAlert } from "./router-BGxBdlkD.mjs";
import { u as useIsDark } from "./use-is-dark-CmoXbbju.mjs";
import { f as formatDate$1, D as DocsContent } from "./use-docs-content-CQG4H0bA.mjs";
import { useForm } from "@tanstack/react-form";
import { toast } from "sonner";
import { A as ApiForm } from "./api-form-BOZocKEu.mjs";
import { I as Input } from "./input-CQnbKF5R.mjs";
import { f as fetchAuthProviders, a as fetchAuthProviderConnections, b as fetchAuthProviderDetail, c as createAuthProviderConnection, d as fetchAuthProviderConnection, e as deleteAuthProviderConnection, u as updateAuthProviderConnection } from "./auth-providers-Djkzae2F.mjs";
import { u as useOrg } from "./org-context-BXR7_uGh.mjs";
import { P as Pencil, T as Trash, L as Link, E as ExternalLink } from "./trash.mjs";
import "@radix-ui/react-alert-dialog";
import "@tanstack/react-router";
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
import "./tabs-ChSqzczQ.mjs";
import "@radix-ui/react-tabs";
function generateRandomSuffix() {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < 6; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}
function generateReadableIdBase(name) {
  if (!name || name.trim() === "") return "";
  let readableId = name.toLowerCase().trim();
  readableId = readableId.replace(/[^a-z0-9\s]/g, "");
  readableId = readableId.replace(/\s+/g, "-");
  readableId = readableId.replace(/-+/g, "-");
  readableId = readableId.replace(/^-|-$/g, "");
  return readableId;
}
function generateReadableId(name, suffix) {
  if (!name || name.trim() === "") return "";
  const base = generateReadableIdBase(name);
  return base ? `${base}-${suffix}` : "";
}
function getAuthProviderIconUrl(shortName, theme) {
  const specialCases = {
    klavis: "klavis.png",
    pipedream: "pipedream.jpeg"
  };
  if (specialCases[shortName]) {
    return `/src/components/icons/auth_providers/${specialCases[shortName]}`;
  }
  if (theme === "dark") {
    return `/src/components/icons/auth_providers/${shortName}-light.svg`;
  } else {
    return `/src/components/icons/auth_providers/${shortName}-dark.svg`;
  }
}
const formatDate = (dateString) => formatDate$1(dateString, "datetime");
const COMING_SOON_PROVIDERS = [
  {
    id: "coming-soon-klavis",
    name: "Klavis",
    short_name: "klavis",
    isComingSoon: true
  }
];
function AuthProviderCard({
  name,
  shortName,
  isConnected = false,
  isComingSoon = false,
  onClick
}) {
  const isDark = useIsDark();
  const handleClick = () => {
    if (isComingSoon) return;
    onClick?.();
  };
  const getColorClass = (name2) => {
    const colors = [
      "bg-blue-500",
      "bg-green-500",
      "bg-purple-500",
      "bg-orange-500",
      "bg-pink-500",
      "bg-indigo-500",
      "bg-red-500",
      "bg-yellow-500"
    ];
    const index = name2.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0) % colors.length;
    return colors[index];
  };
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "relative min-w-[150px] overflow-hidden rounded-lg border transition-all",
        isComingSoon ? "cursor-not-allowed opacity-60" : "group cursor-pointer",
        "border-border hover:border-muted-foreground/30 bg-card hover:bg-accent/50",
        isComingSoon && "hover:border-border hover:bg-card"
      ),
      onClick: handleClick,
      children: /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between p-3 sm:p-4", children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
          /* @__PURE__ */ jsx("div", { className: "flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden rounded-md sm:h-10 sm:w-10", children: /* @__PURE__ */ jsx(
            "img",
            {
              src: getAuthProviderIconUrl(shortName, isDark ? "dark" : "light"),
              alt: `${shortName} icon`,
              className: "h-8 w-8 rounded object-contain sm:h-9 sm:w-9",
              onError: (e) => {
                e.currentTarget.style.display = "none";
                const parent = e.currentTarget.parentElement;
                if (parent) {
                  parent.classList.add(getColorClass(shortName));
                  parent.innerHTML = `<span class="text-white font-semibold text-xs sm:text-sm">${shortName.substring(0, 2).toUpperCase()}</span>`;
                }
              }
            }
          ) }),
          /* @__PURE__ */ jsxs("div", { className: "flex flex-col", children: [
            /* @__PURE__ */ jsx("span", { className: "truncate text-sm font-medium", children: name }),
            isComingSoon && /* @__PURE__ */ jsx("span", { className: "text-muted-foreground text-xs", children: "Coming soon" })
          ] })
        ] }),
        !isComingSoon && /* @__PURE__ */ jsx(
          Button,
          {
            size: "icon",
            variant: "ghost",
            className: cn(
              "h-7 w-7 flex-shrink-0 rounded-full sm:h-8 sm:w-8",
              isConnected ? "bg-green-100 text-green-600 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400 dark:hover:bg-green-800/30" : "bg-muted text-primary hover:bg-primary/10 group-hover:bg-primary/20"
            ),
            children: isConnected ? /* @__PURE__ */ jsx(Check, { className: "h-3.5 w-3.5 sm:h-4 sm:w-4" }) : /* @__PURE__ */ jsx(Plus, { className: "h-3.5 w-3.5 transition-transform group-hover:scale-110 sm:h-4 sm:w-4" })
          }
        )
      ] })
    }
  );
}
const PLATFORM_LINKS = {
  composio: {
    url: "https://platform.composio.dev/",
    label: "Get API Key from Composio"
  },
  pipedream: {
    url: "https://pipedream.com/settings/api",
    label: "Get Client ID & Secret from Pipedream"
  }
};
function AuthFieldsForm({
  providerShortName,
  fields,
  values,
  onChange
}) {
  const isDark = useIsDark();
  const platformLink = PLATFORM_LINKS[providerShortName];
  if (!fields || fields.length === 0) {
    return null;
  }
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4 pt-2", children: [
    /* @__PURE__ */ jsxs("div", { className: "flex items-center justify-between", children: [
      /* @__PURE__ */ jsx("label", { className: "text-muted-foreground text-xs font-medium tracking-wider uppercase", children: "Authentication" }),
      platformLink && /* @__PURE__ */ jsxs(
        Button,
        {
          type: "button",
          variant: "outline",
          size: "sm",
          className: "h-7 text-xs",
          onClick: () => window.open(platformLink.url, "_blank"),
          children: [
            /* @__PURE__ */ jsx(
              "img",
              {
                src: getAuthProviderIconUrl(
                  providerShortName,
                  isDark ? "dark" : "light"
                ),
                alt: providerShortName,
                className: "mr-1.5 h-3 w-3 object-contain"
              }
            ),
            platformLink.label,
            /* @__PURE__ */ jsx(ExternalLink, { className: "ml-1.5 h-3 w-3" })
          ]
        }
      )
    ] }),
    fields.map((field) => /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
      /* @__PURE__ */ jsxs("label", { className: "text-sm font-medium", children: [
        field.title || field.name,
        field.required && /* @__PURE__ */ jsx("span", { className: "text-destructive ml-1", children: "*" })
      ] }),
      field.description && /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-xs", children: field.description }),
      /* @__PURE__ */ jsx(
        Input,
        {
          type: field.secret ? "password" : "text",
          value: values[field.name] || "",
          onChange: (e) => onChange(field.name, e.target.value),
          placeholder: field.secret ? "••••••••" : `Enter ${field.title || field.name}`
        }
      )
    ] }, field.name))
  ] });
}
function ConnectionPreview({
  providerShortName,
  providerName,
  status = "pending"
}) {
  const isDark = useIsDark();
  const statusText = {
    pending: "Waiting for connection...",
    connected: "Connected",
    error: "Connection failed"
  }[status];
  return /* @__PURE__ */ jsx("div", { className: "flex justify-center py-4", children: /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-6", children: [
    /* @__PURE__ */ jsx(
      "div",
      {
        className: cn(
          "flex h-14 w-14 items-center justify-center rounded-xl p-2.5",
          "ring-muted-foreground/20 shadow-lg ring-2",
          "bg-card"
        ),
        children: /* @__PURE__ */ jsx(
          "img",
          {
            src: isDark ? "/airweave-logo-svg-white-darkbg.svg" : "/airweave-logo-svg-lightbg-blacklogo.svg",
            alt: "Airweave",
            className: "h-full w-full object-contain"
          }
        )
      }
    ),
    /* @__PURE__ */ jsx("span", { className: "text-muted-foreground text-sm", children: statusText }),
    /* @__PURE__ */ jsx(
      "div",
      {
        className: cn(
          "flex h-14 w-14 items-center justify-center rounded-xl p-2.5",
          "ring-muted-foreground/20 shadow-lg ring-2",
          "bg-card"
        ),
        children: /* @__PURE__ */ jsx(
          "img",
          {
            src: getAuthProviderIconUrl(
              providerShortName,
              isDark ? "dark" : "light"
            ),
            alt: providerName,
            className: "h-full w-full object-contain"
          }
        )
      }
    )
  ] }) });
}
function ConfigureDialog({
  open,
  onOpenChange,
  authProvider,
  onSuccess,
  orgId
}) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const randomSuffix = useMemo(() => generateRandomSuffix(), [open]);
  const [userEditedId, setUserEditedId] = useState(false);
  const defaultName = authProvider ? `My ${authProvider.name} Connection` : "My Connection";
  const { data: providerDetails, isLoading: isLoadingDetails } = useQuery({
    queryKey: queryKeys.authProviders.detail(
      orgId,
      authProvider?.short_name ?? ""
    ),
    queryFn: async () => {
      if (!authProvider?.short_name) return null;
      const token = await getAccessTokenSilently();
      return fetchAuthProviderDetail(token, orgId, authProvider.short_name);
    },
    enabled: open && !!authProvider?.short_name
  });
  const form = useForm({
    defaultValues: {
      name: defaultName,
      readableId: generateReadableId(defaultName, randomSuffix),
      authFields: {}
    },
    onSubmit: async ({ value }) => {
      createMutation.mutate(value);
    }
  });
  const createMutation = useMutation({
    mutationFn: async (values) => {
      const token = await getAccessTokenSilently();
      return createAuthProviderConnection(token, orgId, {
        name: values.name,
        readable_id: values.readableId,
        short_name: authProvider?.short_name || "",
        auth_fields: values.authFields
      });
    },
    onSuccess: (connection) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.authProviders.connections(orgId)
      });
      toast.success(`Successfully connected to ${authProvider?.name}`, {
        description: "Your connection is now active and ready to use."
      });
      onOpenChange(false);
      form.reset();
      setUserEditedId(false);
      onSuccess?.(connection.readable_id);
    },
    onError: (error) => {
      toast.error("Connection Failed", {
        description: error.message
      });
    }
  });
  const handleNameChange = (newName) => {
    form.setFieldValue("name", newName);
    if (!userEditedId) {
      form.setFieldValue(
        "readableId",
        generateReadableId(newName, randomSuffix)
      );
    }
  };
  const handleReadableIdChange = (newId) => {
    form.setFieldValue("readableId", newId);
    setUserEditedId(true);
  };
  const handleAuthFieldChange = (fieldName, value) => {
    const currentFields = form.getFieldValue("authFields");
    form.setFieldValue("authFields", { ...currentFields, [fieldName]: value });
  };
  const isFormValid = () => {
    const name = form.getFieldValue("name");
    const authFields = form.getFieldValue("authFields");
    if (!name || name.trim() === "") return false;
    if (providerDetails?.auth_fields?.fields) {
      for (const field of providerDetails.auth_fields.fields) {
        if (!authFields[field.name] || authFields[field.name].trim() === "") {
          return false;
        }
      }
    }
    return true;
  };
  const handleClose = (newOpen) => {
    if (!newOpen) {
      form.reset();
      setUserEditedId(false);
    }
    onOpenChange(newOpen);
  };
  if (!authProvider) return null;
  return /* @__PURE__ */ jsx(Dialog, { open, onOpenChange: handleClose, children: /* @__PURE__ */ jsxs(DialogContent, { className: "flex max-h-[90vh] flex-col overflow-hidden sm:max-w-lg", children: [
    /* @__PURE__ */ jsxs(DialogHeader, { children: [
      /* @__PURE__ */ jsxs(DialogTitle, { children: [
        "Connect to ",
        authProvider.name
      ] }),
      /* @__PURE__ */ jsxs(DialogDescription, { children: [
        "Create a connection to ",
        authProvider.name,
        " that can be used to authenticate to data sources"
      ] })
    ] }),
    isLoadingDetails ? /* @__PURE__ */ jsx("div", { className: "flex items-center justify-center py-8", children: /* @__PURE__ */ jsx(LoaderCircle, { className: "text-muted-foreground h-8 w-8 animate-spin" }) }) : /* @__PURE__ */ jsx(
      "form",
      {
        onSubmit: (e) => {
          e.preventDefault();
          form.handleSubmit();
        },
        className: "flex flex-1 flex-col overflow-hidden",
        children: /* @__PURE__ */ jsxs(
          ApiForm,
          {
            method: "POST",
            endpoint: "https://api.airweave.ai/auth-providers/",
            className: "flex flex-1 flex-col overflow-hidden",
            body: {
              name: form.getFieldValue("name"),
              readable_id: form.getFieldValue("readableId"),
              short_name: authProvider.short_name,
              auth_fields: form.getFieldValue("authFields")
            },
            onBodyChange: (newBody) => {
              if (typeof newBody.name === "string") {
                form.setFieldValue("name", newBody.name);
              }
              if (typeof newBody.readable_id === "string") {
                form.setFieldValue("readableId", newBody.readable_id);
                setUserEditedId(true);
              }
              if (newBody.auth_fields && typeof newBody.auth_fields === "object") {
                form.setFieldValue(
                  "authFields",
                  newBody.auth_fields
                );
              }
            },
            children: [
              /* @__PURE__ */ jsx(ApiForm.Toggle, {}),
              /* @__PURE__ */ jsxs(ApiForm.FormView, { className: "flex-1 space-y-6 overflow-y-auto", children: [
                /* @__PURE__ */ jsx(
                  ConnectionPreview,
                  {
                    providerShortName: authProvider.short_name,
                    providerName: authProvider.name,
                    status: "pending"
                  }
                ),
                /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
                  /* @__PURE__ */ jsx("label", { className: "text-muted-foreground text-xs font-medium tracking-wider uppercase", children: "Name" }),
                  /* @__PURE__ */ jsx(form.Field, { name: "name", children: (field) => /* @__PURE__ */ jsx(
                    Input,
                    {
                      value: field.state.value,
                      onChange: (e) => handleNameChange(e.target.value),
                      placeholder: "My Connection"
                    }
                  ) })
                ] }),
                /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
                  /* @__PURE__ */ jsx("label", { className: "text-muted-foreground text-xs font-medium tracking-wider uppercase", children: "Readable ID" }),
                  /* @__PURE__ */ jsx(form.Field, { name: "readableId", children: (field) => /* @__PURE__ */ jsx(
                    Input,
                    {
                      value: field.state.value,
                      onChange: (e) => handleReadableIdChange(e.target.value),
                      placeholder: "Auto-generated",
                      className: "font-mono text-sm"
                    }
                  ) })
                ] }),
                providerDetails?.auth_fields?.fields && /* @__PURE__ */ jsx(
                  AuthFieldsForm,
                  {
                    providerShortName: authProvider.short_name,
                    fields: providerDetails.auth_fields.fields,
                    values: form.getFieldValue("authFields"),
                    onChange: handleAuthFieldChange
                  }
                )
              ] }),
              /* @__PURE__ */ jsx(ApiForm.CodeView, { editable: true, className: "flex-1 overflow-y-auto" }),
              /* @__PURE__ */ jsxs(ApiForm.Footer, { className: "border-t pt-4", children: [
                /* @__PURE__ */ jsx(
                  Button,
                  {
                    type: "button",
                    variant: "outline",
                    onClick: () => handleClose(false),
                    disabled: createMutation.isPending,
                    children: "Cancel"
                  }
                ),
                /* @__PURE__ */ jsx(
                  Button,
                  {
                    type: "submit",
                    disabled: createMutation.isPending || !isFormValid(),
                    children: createMutation.isPending ? /* @__PURE__ */ jsxs(Fragment, { children: [
                      /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 h-4 w-4 animate-spin" }),
                      "Connecting..."
                    ] }) : "Connect"
                  }
                )
              ] })
            ]
          }
        )
      }
    )
  ] }) });
}
function DeleteConfirmationDialog({
  open,
  onOpenChange,
  title,
  confirmValue,
  onConfirm,
  isDeleting = false,
  deletedItems = [],
  criticalWarning,
  deleteButtonText = "Delete"
}) {
  const [confirmText, setConfirmText] = useState("");
  const isConfirmValid = confirmText === confirmValue;
  const handleOpenChange = (newOpen) => {
    if (!newOpen) {
      setConfirmText("");
    }
    onOpenChange(newOpen);
  };
  const handleConfirm = () => {
    if (!isConfirmValid) return;
    onConfirm();
  };
  return /* @__PURE__ */ jsx(AlertDialog, { open, onOpenChange: handleOpenChange, children: /* @__PURE__ */ jsxs(AlertDialogContent, { className: "sm:max-w-md", children: [
    /* @__PURE__ */ jsxs(AlertDialogHeader, { className: "space-y-4", children: [
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
        /* @__PURE__ */ jsx("div", { className: "bg-destructive/10 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full", children: /* @__PURE__ */ jsx(TriangleAlert, { className: "text-destructive h-5 w-5" }) }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx(AlertDialogTitle, { children: title }),
          /* @__PURE__ */ jsx("p", { className: "text-muted-foreground mt-1 text-sm", children: "This action cannot be undone" })
        ] })
      ] }),
      /* @__PURE__ */ jsx(AlertDialogDescription, { asChild: true, children: /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
        deletedItems.length > 0 && /* @__PURE__ */ jsxs("div", { className: "bg-destructive/5 border-destructive/20 rounded-lg border p-4", children: [
          /* @__PURE__ */ jsx("p", { className: "text-foreground mb-3 font-medium", children: "This will permanently delete:" }),
          /* @__PURE__ */ jsx("ul", { className: "text-muted-foreground space-y-2 text-sm", children: deletedItems.map((item, index) => /* @__PURE__ */ jsxs("li", { className: "flex items-start gap-2", children: [
            /* @__PURE__ */ jsx("div", { className: "bg-destructive/60 mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full" }),
            /* @__PURE__ */ jsx("span", { children: item })
          ] }, index)) })
        ] }),
        criticalWarning && /* @__PURE__ */ jsx("div", { className: "rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/20", children: /* @__PURE__ */ jsxs("div", { className: "flex items-start gap-2", children: [
          /* @__PURE__ */ jsx(CircleAlert, { className: "mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600 dark:text-amber-400" }),
          /* @__PURE__ */ jsxs("div", { className: "text-sm", children: [
            /* @__PURE__ */ jsx("p", { className: "mb-1 font-medium text-amber-800 dark:text-amber-200", children: criticalWarning.title }),
            /* @__PURE__ */ jsx("p", { className: "text-amber-700 dark:text-amber-300", children: criticalWarning.description })
          ] })
        ] }) }),
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
                  /* @__PURE__ */ jsx("span", { className: "text-destructive bg-destructive/10 rounded px-1.5 py-0.5 font-mono font-semibold", children: confirmValue }),
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
                disabled: isDeleting,
                className: cn(
                  "transition-colors",
                  isConfirmValid && confirmText.length > 0 ? "border-green-500 focus-visible:ring-green-500/20" : confirmText.length > 0 ? "border-destructive focus-visible:ring-destructive/20" : ""
                ),
                placeholder: confirmValue
              }
            )
          ] }),
          confirmText.length > 0 && !isDeleting && /* @__PURE__ */ jsx("div", { className: "flex items-center gap-2 text-sm", children: isConfirmValid ? /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx(Check, { className: "h-4 w-4 text-green-500" }),
            /* @__PURE__ */ jsx("span", { className: "text-green-600 dark:text-green-400", children: "Confirmation matches" })
          ] }) : /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx(CircleAlert, { className: "text-destructive h-4 w-4" }),
            /* @__PURE__ */ jsx("span", { className: "text-destructive", children: "Confirmation does not match" })
          ] }) })
        ] })
      ] }) })
    ] }),
    /* @__PURE__ */ jsxs(AlertDialogFooter, { className: "gap-3", children: [
      /* @__PURE__ */ jsx(
        AlertDialogCancel,
        {
          disabled: isDeleting,
          onClick: () => setConfirmText(""),
          children: "Cancel"
        }
      ),
      /* @__PURE__ */ jsx(
        AlertDialogAction,
        {
          onClick: handleConfirm,
          disabled: !isConfirmValid || isDeleting,
          className: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
          children: isDeleting ? /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 h-4 w-4 animate-spin" }),
            "Deleting..."
          ] }) : /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx(Trash, { className: "mr-2 h-4 w-4" }),
            deleteButtonText
          ] })
        }
      )
    ] })
  ] }) });
}
function DetailDialog({
  open,
  onOpenChange,
  authProvider,
  connection,
  onEdit,
  orgId
}) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const [copiedField, setCopiedField] = useState(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const isDark = useIsDark();
  const { data: connectionDetails, isLoading } = useQuery({
    queryKey: queryKeys.authProviders.connection(
      orgId,
      connection?.readable_id ?? ""
    ),
    queryFn: async () => {
      if (!connection?.readable_id) return null;
      const token = await getAccessTokenSilently();
      return fetchAuthProviderConnection(token, orgId, connection.readable_id);
    },
    enabled: open && !!connection?.readable_id
  });
  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!connection?.readable_id) return;
      const token = await getAccessTokenSilently();
      return deleteAuthProviderConnection(token, orgId, connection.readable_id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.authProviders.connections(orgId)
      });
      toast.success("Auth provider connection deleted successfully");
      setShowDeleteDialog(false);
      onOpenChange(false);
    },
    onError: (error) => {
      toast.error(error.message);
    }
  });
  const handleCopy = async (value, fieldName) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedField(fieldName);
      toast.success(`${fieldName} copied to clipboard`);
      setTimeout(() => setCopiedField(null), 2e3);
    } catch {
      toast.error("Failed to copy to clipboard");
    }
  };
  const handleClose = (newOpen) => {
    if (!newOpen) {
      setCopiedField(null);
    }
    onOpenChange(newOpen);
  };
  if (!authProvider || !connection) return null;
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(Dialog, { open, onOpenChange: handleClose, children: /* @__PURE__ */ jsxs(DialogContent, { className: "flex max-h-[90vh] flex-col overflow-hidden sm:max-w-lg", children: [
      /* @__PURE__ */ jsxs(DialogHeader, { className: "flex flex-row items-start justify-between space-y-0", children: [
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsxs(DialogTitle, { children: [
            authProvider.name,
            " Connection"
          ] }),
          /* @__PURE__ */ jsxs(DialogDescription, { children: [
            "View and manage your ",
            authProvider.name,
            " connection details"
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex gap-1", children: [
          /* @__PURE__ */ jsx(
            Button,
            {
              variant: "ghost",
              size: "icon",
              className: "h-8 w-8",
              onClick: onEdit,
              title: "Edit connection",
              children: /* @__PURE__ */ jsx(Pencil, { className: "h-4 w-4" })
            }
          ),
          /* @__PURE__ */ jsx(
            Button,
            {
              variant: "ghost",
              size: "icon",
              className: "hover:text-destructive h-8 w-8",
              onClick: () => setShowDeleteDialog(true),
              title: "Delete connection",
              children: /* @__PURE__ */ jsx(Trash, { className: "h-4 w-4" })
            }
          )
        ] })
      ] }),
      isLoading ? /* @__PURE__ */ jsx("div", { className: "flex items-center justify-center py-8", children: /* @__PURE__ */ jsx(LoaderCircle, { className: "text-muted-foreground h-8 w-8 animate-spin" }) }) : connectionDetails ? /* @__PURE__ */ jsxs("div", { className: "flex-1 space-y-6 overflow-y-auto py-4", children: [
        /* @__PURE__ */ jsx("div", { className: "flex justify-center py-4", children: /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-8", children: [
          /* @__PURE__ */ jsxs("div", { className: "relative", children: [
            /* @__PURE__ */ jsx(
              "div",
              {
                className: cn(
                  "flex h-14 w-14 items-center justify-center rounded-xl p-2.5",
                  "shadow-lg ring-2 ring-green-400/30",
                  "bg-card"
                ),
                children: /* @__PURE__ */ jsx(
                  "img",
                  {
                    src: isDark ? "/airweave-logo-svg-white-darkbg.svg" : "/airweave-logo-svg-lightbg-blacklogo.svg",
                    alt: "Airweave",
                    className: "h-full w-full object-contain"
                  }
                )
              }
            ),
            /* @__PURE__ */ jsx("div", { className: "absolute -right-1 -bottom-1", children: /* @__PURE__ */ jsx(
              "div",
              {
                className: cn(
                  "flex h-5 w-5 items-center justify-center rounded-full border-2",
                  "bg-background border-green-500"
                ),
                children: /* @__PURE__ */ jsx(Link, { className: "h-2.5 w-2.5 text-green-500" })
              }
            ) })
          ] }),
          /* @__PURE__ */ jsx("span", { className: "text-sm font-medium text-green-600 dark:text-green-400", children: "Active Connection" }),
          /* @__PURE__ */ jsxs("div", { className: "relative", children: [
            /* @__PURE__ */ jsx(
              "div",
              {
                className: cn(
                  "flex h-14 w-14 items-center justify-center rounded-xl p-2.5",
                  "shadow-lg ring-2 ring-green-400/30",
                  "bg-card"
                ),
                children: /* @__PURE__ */ jsx(
                  "img",
                  {
                    src: getAuthProviderIconUrl(
                      authProvider.short_name,
                      isDark ? "dark" : "light"
                    ),
                    alt: authProvider.name,
                    className: "h-full w-full object-contain"
                  }
                )
              }
            ),
            /* @__PURE__ */ jsx("div", { className: "absolute -right-1 -bottom-1", children: /* @__PURE__ */ jsx(
              "div",
              {
                className: cn(
                  "flex h-5 w-5 items-center justify-center rounded-full border-2",
                  "bg-background border-green-500"
                ),
                children: /* @__PURE__ */ jsx(Link, { className: "h-2.5 w-2.5 text-green-500" })
              }
            ) })
          ] })
        ] }) }),
        /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
          /* @__PURE__ */ jsx(DetailField, { label: "Name", value: connectionDetails.name }),
          /* @__PURE__ */ jsx(
            DetailField,
            {
              label: "Readable ID",
              value: connectionDetails.readable_id,
              mono: true,
              copyable: true,
              onCopy: () => handleCopy(connectionDetails.readable_id, "Readable ID"),
              copied: copiedField === "Readable ID"
            }
          ),
          connectionDetails.created_by_email && /* @__PURE__ */ jsx(
            DetailField,
            {
              label: "Created By",
              value: connectionDetails.created_by_email
            }
          ),
          /* @__PURE__ */ jsx(
            DetailField,
            {
              label: "Created At",
              value: formatDate(connectionDetails.created_at)
            }
          ),
          /* @__PURE__ */ jsx(
            DetailField,
            {
              label: "Modified At",
              value: formatDate(connectionDetails.modified_at)
            }
          ),
          connectionDetails.masked_client_id && /* @__PURE__ */ jsx(
            DetailField,
            {
              label: "Client ID",
              value: connectionDetails.masked_client_id,
              mono: true,
              copyable: true,
              onCopy: () => handleCopy(
                connectionDetails.masked_client_id,
                "Client ID"
              ),
              copied: copiedField === "Client ID"
            }
          )
        ] })
      ] }) : /* @__PURE__ */ jsx("div", { className: "text-muted-foreground py-8 text-center", children: "No connection details available" }),
      /* @__PURE__ */ jsx(DialogFooter, { className: "border-t pt-4", children: /* @__PURE__ */ jsx(
        Button,
        {
          variant: "outline",
          onClick: () => handleClose(false),
          className: "w-full",
          children: "Done"
        }
      ) })
    ] }) }),
    /* @__PURE__ */ jsx(
      DeleteConfirmationDialog,
      {
        open: showDeleteDialog,
        onOpenChange: setShowDeleteDialog,
        title: "Delete Auth Provider Connection",
        confirmValue: connectionDetails?.readable_id ?? "",
        onConfirm: () => deleteMutation.mutate(),
        isDeleting: deleteMutation.isPending,
        deletedItems: [
          "This auth provider connection",
          "All source connections using this auth provider",
          "All associated sync configurations and data"
        ],
        criticalWarning: {
          title: "Critical Impact",
          description: "Source connections will stop working immediately and cannot be recovered."
        },
        deleteButtonText: "Delete Connection"
      }
    )
  ] });
}
function DetailField({
  label,
  value,
  mono,
  copyable,
  onCopy,
  copied
}) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
    /* @__PURE__ */ jsx("label", { className: "text-muted-foreground text-xs font-medium tracking-wider uppercase", children: label }),
    /* @__PURE__ */ jsxs(
      "div",
      {
        className: cn(
          "bg-muted/50 rounded-md border px-3 py-2 text-sm",
          copyable && "group flex items-center justify-between"
        ),
        children: [
          /* @__PURE__ */ jsx("span", { className: cn(mono && "font-mono break-all"), children: value }),
          copyable && onCopy && /* @__PURE__ */ jsx(
            Button,
            {
              variant: "ghost",
              size: "icon",
              className: "h-6 w-6 opacity-0 transition-opacity group-hover:opacity-100",
              onClick: onCopy,
              children: copied ? /* @__PURE__ */ jsx(Check, { className: "h-3.5 w-3.5 text-green-500" }) : /* @__PURE__ */ jsx(Copy, { className: "h-3.5 w-3.5" })
            }
          )
        ]
      }
    )
  ] });
}
function EditDialog({
  open,
  onOpenChange,
  authProvider,
  connection,
  onSuccess,
  orgId
}) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const isDark = useIsDark();
  const { data: connectionDetails, isLoading: isLoadingConnection } = useQuery({
    queryKey: queryKeys.authProviders.connection(
      orgId,
      connection?.readable_id ?? ""
    ),
    queryFn: async () => {
      if (!connection?.readable_id) return null;
      const token = await getAccessTokenSilently();
      return fetchAuthProviderConnection(token, orgId, connection.readable_id);
    },
    enabled: open && !!connection?.readable_id
  });
  const { data: providerDetails, isLoading: isLoadingProvider } = useQuery({
    queryKey: queryKeys.authProviders.detail(
      orgId,
      authProvider?.short_name ?? ""
    ),
    queryFn: async () => {
      if (!authProvider?.short_name) return null;
      const token = await getAccessTokenSilently();
      return fetchAuthProviderDetail(token, orgId, authProvider.short_name);
    },
    enabled: open && !!authProvider?.short_name
  });
  const isLoading = isLoadingConnection || isLoadingProvider;
  if (!authProvider || !connection) return null;
  return /* @__PURE__ */ jsx(Dialog, { open, onOpenChange, children: /* @__PURE__ */ jsxs(DialogContent, { className: "flex max-h-[90vh] flex-col overflow-hidden sm:max-w-lg", children: [
    /* @__PURE__ */ jsxs(DialogHeader, { children: [
      /* @__PURE__ */ jsxs(DialogTitle, { children: [
        "Edit ",
        authProvider.name,
        " Connection"
      ] }),
      /* @__PURE__ */ jsx(DialogDescription, { children: "Update your connection details. Leave fields empty to keep current values." })
    ] }),
    isLoading ? /* @__PURE__ */ jsx("div", { className: "flex items-center justify-center py-8", children: /* @__PURE__ */ jsx(LoaderCircle, { className: "text-muted-foreground h-8 w-8 animate-spin" }) }) : /* @__PURE__ */ jsx(
      EditDialogForm,
      {
        authProvider,
        connection,
        connectionDetails,
        providerDetails,
        orgId,
        isDark,
        queryClient,
        getAccessTokenSilently,
        onOpenChange,
        onSuccess
      },
      connection.readable_id
    )
  ] }) });
}
function EditDialogForm({
  authProvider,
  connection,
  connectionDetails,
  providerDetails,
  orgId,
  isDark,
  queryClient,
  getAccessTokenSilently,
  onOpenChange,
  onSuccess
}) {
  const form = useForm({
    defaultValues: {
      name: connectionDetails?.name ?? "",
      authFields: {}
    },
    onSubmit: async ({ value }) => {
      updateMutation.mutate(value);
    }
  });
  const updateMutation = useMutation({
    mutationFn: async (values) => {
      if (!connection?.readable_id) throw new Error("No connection ID");
      const token = await getAccessTokenSilently();
      const updateData = {};
      if (values.name && values.name !== connectionDetails?.name) {
        updateData.name = values.name;
      }
      const filledAuthFields = Object.entries(values.authFields).filter(([, value]) => value && String(value).trim() !== "").reduce(
        (acc, [key, value]) => ({ ...acc, [key]: value }),
        {}
      );
      if (Object.keys(filledAuthFields).length > 0) {
        updateData.auth_fields = filledAuthFields;
      }
      if (Object.keys(updateData).length === 0) {
        return null;
      }
      return updateAuthProviderConnection(
        token,
        orgId,
        connection.readable_id,
        updateData
      );
    },
    onSuccess: (result) => {
      if (result === null) {
        toast.info("No changes to update");
        onOpenChange(false);
        return;
      }
      queryClient.invalidateQueries({
        queryKey: queryKeys.authProviders.connections(orgId)
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.authProviders.connection(
          orgId,
          connection?.readable_id ?? ""
        )
      });
      toast.success(`Successfully updated ${authProvider?.name} connection`);
      onOpenChange(false);
      form.reset();
      onSuccess?.();
    },
    onError: (error) => {
      toast.error(error.message);
    }
  });
  const handleAuthFieldChange = (fieldName, value) => {
    const currentFields = form.getFieldValue("authFields");
    form.setFieldValue("authFields", { ...currentFields, [fieldName]: value });
  };
  const handleClose = () => {
    form.reset();
    onOpenChange(false);
  };
  return /* @__PURE__ */ jsxs(
    "form",
    {
      onSubmit: (e) => {
        e.preventDefault();
        form.handleSubmit();
      },
      className: "flex flex-1 flex-col overflow-hidden",
      children: [
        /* @__PURE__ */ jsxs("div", { className: "flex-1 space-y-6 overflow-y-auto py-4", children: [
          /* @__PURE__ */ jsx("div", { className: "flex justify-center py-4", children: /* @__PURE__ */ jsx(
            "div",
            {
              className: cn(
                "flex h-20 w-20 items-center justify-center rounded-xl p-3",
                "border shadow-sm",
                "bg-card"
              ),
              children: /* @__PURE__ */ jsx(
                "img",
                {
                  src: getAuthProviderIconUrl(
                    authProvider.short_name,
                    isDark ? "dark" : "light"
                  ),
                  alt: authProvider.name,
                  className: "h-full w-full object-contain"
                }
              )
            }
          ) }),
          /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
            /* @__PURE__ */ jsx("label", { className: "text-sm font-medium", children: "Name" }),
            /* @__PURE__ */ jsx(form.Field, { name: "name", children: (field) => /* @__PURE__ */ jsx(
              Input,
              {
                value: field.state.value,
                onChange: (e) => field.handleChange(e.target.value),
                placeholder: connectionDetails?.name || "Connection name"
              }
            ) })
          ] }),
          providerDetails?.auth_fields?.fields && providerDetails.auth_fields.fields.length > 0 && /* @__PURE__ */ jsxs("div", { className: "space-y-4 pt-2", children: [
            /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Update authentication credentials (leave empty to keep current values)" }),
            providerDetails.auth_fields.fields.map((field) => /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
              /* @__PURE__ */ jsx("label", { className: "text-sm font-medium", children: field.title || field.name }),
              field.description && /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-xs", children: field.description }),
              /* @__PURE__ */ jsx(form.Field, { name: "authFields", children: () => /* @__PURE__ */ jsx(
                Input,
                {
                  type: field.secret ? "password" : "text",
                  value: form.getFieldValue("authFields")[field.name] || "",
                  onChange: (e) => handleAuthFieldChange(field.name, e.target.value),
                  placeholder: field.secret ? "••••••••" : `Enter new ${field.title || field.name}`
                }
              ) })
            ] }, field.name))
          ] })
        ] }),
        /* @__PURE__ */ jsxs(DialogFooter, { className: "border-t pt-4", children: [
          /* @__PURE__ */ jsx(
            Button,
            {
              type: "button",
              variant: "outline",
              onClick: handleClose,
              disabled: updateMutation.isPending,
              children: "Cancel"
            }
          ),
          /* @__PURE__ */ jsx(Button, { type: "submit", disabled: updateMutation.isPending, children: updateMutation.isPending ? /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 h-4 w-4 animate-spin" }),
            "Updating..."
          ] }) : "Update" })
        ] })
      ]
    }
  );
}
function AuthProvidersDocs() {
  return /* @__PURE__ */ jsx(DocsContent, { docPath: "auth-providers/overview.mdx" });
}
function AuthProvidersCode() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "Auth Provider Setup" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Configure authentication for your source connections:" }),
    /* @__PURE__ */ jsx("pre", { className: "bg-muted overflow-auto rounded-lg p-3 text-xs", children: /* @__PURE__ */ jsx("code", { children: `// Using OAuth flow with Composio
const connection = await client.sourceConnections.create({
  name: 'My Notion Connection',
  short_name: 'notion',
  collection_id: collection.readable_id,
  authentication: {
    auth_provider: 'composio',
    // OAuth flow handled automatically
  }
});

// Using OAuth flow with Pipedream
const connection = await client.sourceConnections.create({
  name: 'My Slack Connection',
  short_name: 'slack',
  collection_id: collection.readable_id,
  authentication: {
    auth_provider: 'pipedream',
  }
});` }) })
  ] });
}
function AuthProvidersHelp() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "About Auth Providers" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Auth providers help manage OAuth connections to external services, allowing Airweave to securely authenticate with your data sources." }),
    /* @__PURE__ */ jsxs("div", { className: "space-y-3", children: [
      /* @__PURE__ */ jsxs("div", { className: "bg-muted rounded-lg p-3", children: [
        /* @__PURE__ */ jsx("h4", { className: "text-sm font-medium", children: "Supported Providers" }),
        /* @__PURE__ */ jsxs("ul", { className: "text-muted-foreground mt-2 space-y-1.5 text-xs", children: [
          /* @__PURE__ */ jsxs("li", { className: "flex items-start gap-2", children: [
            /* @__PURE__ */ jsx("span", { className: "text-foreground font-medium", children: "Composio" }),
            /* @__PURE__ */ jsx("span", { children: "- Multi-app OAuth with 100+ integrations" })
          ] }),
          /* @__PURE__ */ jsxs("li", { className: "flex items-start gap-2", children: [
            /* @__PURE__ */ jsx("span", { className: "text-foreground font-medium", children: "Pipedream" }),
            /* @__PURE__ */ jsx("span", { children: "- Workflow automation with OAuth support" })
          ] }),
          /* @__PURE__ */ jsxs("li", { className: "flex items-start gap-2", children: [
            /* @__PURE__ */ jsx("span", { className: "text-foreground text-muted-foreground font-medium", children: "Klavis" }),
            /* @__PURE__ */ jsx("span", { className: "text-muted-foreground/70", children: "- MCP-native authentication (coming soon)" })
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "bg-muted rounded-lg p-3", children: [
        /* @__PURE__ */ jsx("h4", { className: "text-sm font-medium", children: "How it works" }),
        /* @__PURE__ */ jsxs("ol", { className: "text-muted-foreground mt-2 list-inside list-decimal space-y-1.5 text-xs", children: [
          /* @__PURE__ */ jsx("li", { children: "Create an auth provider connection with your API keys" }),
          /* @__PURE__ */ jsx("li", { children: "When creating a source connection, select the auth provider" }),
          /* @__PURE__ */ jsx("li", { children: "Users authenticate via OAuth through the provider's secure flow" }),
          /* @__PURE__ */ jsx("li", { children: "Tokens are securely stored and automatically refreshed" })
        ] })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "bg-muted rounded-lg p-3", children: [
        /* @__PURE__ */ jsx("h4", { className: "text-sm font-medium", children: "Getting Started" }),
        /* @__PURE__ */ jsxs("div", { className: "text-muted-foreground mt-2 space-y-2 text-xs", children: [
          /* @__PURE__ */ jsxs("p", { children: [
            /* @__PURE__ */ jsx("span", { className: "text-foreground font-medium", children: "Composio:" }),
            " ",
            "Sign up at",
            " ",
            /* @__PURE__ */ jsx(
              "a",
              {
                href: "https://platform.composio.dev",
                target: "_blank",
                rel: "noopener noreferrer",
                className: "text-primary hover:underline",
                children: "platform.composio.dev"
              }
            ),
            " ",
            "and get your API key from the dashboard."
          ] }),
          /* @__PURE__ */ jsxs("p", { children: [
            /* @__PURE__ */ jsx("span", { className: "text-foreground font-medium", children: "Pipedream:" }),
            " ",
            "Get your Client ID and Secret from",
            " ",
            /* @__PURE__ */ jsx(
              "a",
              {
                href: "https://pipedream.com/settings/api",
                target: "_blank",
                rel: "noopener noreferrer",
                className: "text-primary hover:underline",
                children: "pipedream.com/settings/api"
              }
            )
          ] })
        ] })
      ] })
    ] })
  ] });
}
function AuthProvidersPage() {
  const {
    getAccessTokenSilently
  } = useAuth0();
  const {
    organization
  } = useOrg();
  if (!organization) {
    throw new Error("Organization context is required but not available");
  }
  const orgId = organization.id;
  const [dialogMode, setDialogMode] = useState(null);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [selectedConnection, setSelectedConnection] = useState(null);
  usePageHeader({
    title: "Auth Providers",
    description: "Authenticate data sources through third-party applications"
  });
  useRightSidebarContent({
    docs: /* @__PURE__ */ jsx(AuthProvidersDocs, {}),
    code: /* @__PURE__ */ jsx(AuthProvidersCode, {}),
    help: /* @__PURE__ */ jsx(AuthProvidersHelp, {})
  });
  const {
    data: authProviders,
    isLoading: isLoadingProviders,
    error: providersError
  } = useQuery({
    queryKey: queryKeys.authProviders.list(orgId),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchAuthProviders(token, orgId);
    }
  });
  const {
    data: connections,
    isLoading: isLoadingConnections,
    error: connectionsError
  } = useQuery({
    queryKey: queryKeys.authProviders.connections(orgId),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchAuthProviderConnections(token, orgId);
    }
  });
  const allProviders = useMemo(() => {
    if (!authProviders) return COMING_SOON_PROVIDERS;
    return [...authProviders, ...COMING_SOON_PROVIDERS];
  }, [authProviders]);
  const getConnectionForProvider = (shortName) => {
    return connections?.find((conn) => conn.short_name === shortName);
  };
  const handleProviderClick = (provider) => {
    if ("isComingSoon" in provider && provider.isComingSoon) return;
    const connection = getConnectionForProvider(provider.short_name);
    if (connection) {
      setSelectedProvider(provider);
      setSelectedConnection(connection);
      setDialogMode("detail");
    } else {
      setSelectedProvider(provider);
      setSelectedConnection(null);
      setDialogMode("configure");
    }
  };
  const handleDialogClose = () => {
    setDialogMode(null);
    setSelectedProvider(null);
    setSelectedConnection(null);
  };
  const handleEdit = () => {
    setDialogMode("edit");
  };
  const handleConfigureSuccess = (connectionId) => {
    const newConnection = connections?.find((conn) => conn.readable_id === connectionId);
    if (newConnection && selectedProvider) {
      setSelectedConnection(newConnection);
      setDialogMode("detail");
    } else {
      handleDialogClose();
    }
  };
  const handleEditSuccess = () => {
    setDialogMode("detail");
  };
  const isLoading = isLoadingProviders || isLoadingConnections;
  const error = providersError || connectionsError;
  if (isLoading) {
    return /* @__PURE__ */ jsx("div", { className: "p-6", children: /* @__PURE__ */ jsx(LoadingState, {}) });
  }
  if (error) {
    return /* @__PURE__ */ jsx("div", { className: "p-6", children: /* @__PURE__ */ jsx(ErrorState, { error: error instanceof Error ? error : "Failed to load auth providers" }) });
  }
  if (allProviders.length === 0) {
    return /* @__PURE__ */ jsx("div", { className: "p-6", children: /* @__PURE__ */ jsx(EmptyState, { icon: /* @__PURE__ */ jsx(ShieldCheck, {}), title: "No auth providers available", description: "Auth providers enable secure OAuth connections to external services." }) });
  }
  return /* @__PURE__ */ jsxs("div", { className: "p-6", children: [
    /* @__PURE__ */ jsx("div", { className: "grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3", children: allProviders.map((provider) => {
      const connection = getConnectionForProvider(provider.short_name);
      const isComingSoon = "isComingSoon" in provider && provider.isComingSoon;
      return /* @__PURE__ */ jsx(AuthProviderCard, { id: provider.id, name: provider.name, shortName: provider.short_name, isConnected: !!connection, isComingSoon, onClick: () => handleProviderClick(provider) }, provider.id);
    }) }),
    /* @__PURE__ */ jsx(ConfigureDialog, { open: dialogMode === "configure", onOpenChange: (open) => {
      if (!open) handleDialogClose();
    }, authProvider: selectedProvider, onSuccess: handleConfigureSuccess, orgId }),
    /* @__PURE__ */ jsx(DetailDialog, { open: dialogMode === "detail", onOpenChange: (open) => {
      if (!open) handleDialogClose();
    }, authProvider: selectedProvider, connection: selectedConnection, onEdit: handleEdit, orgId }),
    /* @__PURE__ */ jsx(EditDialog, { open: dialogMode === "edit", onOpenChange: (open) => {
      if (!open) {
        setDialogMode("detail");
      }
    }, authProvider: selectedProvider, connection: selectedConnection, onSuccess: handleEditSuccess, orgId })
  ] });
}
export {
  AuthProvidersPage as component
};
