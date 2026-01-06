import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import { useQueryClient, useInfiniteQuery, useMutation } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { toast } from "sonner";
import { u as useAuth0, a9 as usePageHeader, aa as useRightSidebarContent, q as queryKeys, ai as useCommandMenu, B as Button, P as Plus, aj as Key, L as LoaderCircle, D as Dialog, k as DialogContent, l as DialogHeader, m as DialogTitle, n as DialogDescription, a as cn, ak as CircleCheck, E as DropdownMenu, F as DropdownMenuTrigger, G as DropdownMenuContent, K as DropdownMenuItem } from "./router-BGxBdlkD.mjs";
import { E as EmptyState } from "./empty-state-BldPO3ai.mjs";
import { E as ErrorState, C as Copy, A as AlertDialog, b as AlertDialogContent, c as AlertDialogHeader, d as AlertDialogTitle, e as AlertDialogDescription, f as AlertDialogFooter, g as AlertDialogCancel, h as AlertDialogAction } from "./error-state-BYmPP-hR.mjs";
import { L as LoadingState } from "./loading-state-CJE8ekwd.mjs";
import { f as fetchApiKeys, d as deleteApiKey, c as createApiKey } from "./api-keys-DlD7J9DW.mjs";
import { u as useOrg } from "./org-context-BXR7_uGh.mjs";
import { B as Badge } from "./badge-B1TPqLQ8.mjs";
import { g as getSelectionColumn, D as DataTable, a as DataTableFloatingToolbar, b as Download, E as Ellipsis, B as Braces } from "./data-table-floating-toolbar-BlF-76To.mjs";
import { f as formatDate$1, g as getDaysFromNow, D as DocsContent } from "./use-docs-content-CQG4H0bA.mjs";
import { useForm } from "@tanstack/react-form";
import { A as ApiForm } from "./api-form-BOZocKEu.mjs";
import { T as Trash2 } from "./trash-2.mjs";
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
import "@radix-ui/react-alert-dialog";
import "./checkbox-L51m4-da.mjs";
import "@radix-ui/react-checkbox";
import "@tanstack/react-table";
import "./tabs-ChSqzczQ.mjs";
import "@radix-ui/react-tabs";
const EXPIRATION_PRESETS = [
  { days: 30, label: "30 days" },
  { days: 60, label: "60 days" },
  { days: 90, label: "90 days", recommended: true },
  { days: 180, label: "180 days" },
  { days: 365, label: "365 days" }
];
function maskKey(key) {
  if (!key || key.length < 8) return key;
  return `${key.substring(0, 8)}${"•".repeat(32)}`;
}
const getDaysRemaining = getDaysFromNow;
function getStatusColor(daysRemaining) {
  if (daysRemaining < 0) return "text-red-500";
  if (daysRemaining <= 7) return "text-amber-500";
  return "text-muted-foreground";
}
const formatDate = (dateString) => formatDate$1(dateString, "short");
function getApiKeyActions(options) {
  return [
    {
      id: "copy-json",
      label: "Copy as JSON",
      onSelect: options.onCopyAsJson
    },
    {
      id: "delete-key",
      label: "Delete API key",
      variant: "destructive",
      onSelect: options.onDelete
    }
  ];
}
function DeleteApiKeyDialog({
  open,
  onOpenChange,
  keys,
  onConfirm
}) {
  const count = keys.length;
  const isMultiple = count > 1;
  if (count === 0) return null;
  return /* @__PURE__ */ jsx(AlertDialog, { open, onOpenChange, children: /* @__PURE__ */ jsxs(AlertDialogContent, { className: "sm:max-w-md", children: [
    /* @__PURE__ */ jsxs(AlertDialogHeader, { children: [
      /* @__PURE__ */ jsxs(AlertDialogTitle, { children: [
        "Delete ",
        isMultiple ? `${count} API keys` : "API key"
      ] }),
      /* @__PURE__ */ jsxs(AlertDialogDescription, { children: [
        "This action cannot be undone. Any applications using",
        " ",
        isMultiple ? "these keys" : "this key",
        " will lose access immediately."
      ] })
    ] }),
    /* @__PURE__ */ jsx(
      "div",
      {
        className: `bg-muted my-4 rounded-lg border p-3 ${isMultiple ? "max-h-32 space-y-1 overflow-y-auto" : ""}`,
        children: keys.map((key) => /* @__PURE__ */ jsx("code", { className: "block font-mono text-sm", children: maskKey(key.decrypted_key) }, key.id))
      }
    ),
    /* @__PURE__ */ jsxs(AlertDialogFooter, { children: [
      /* @__PURE__ */ jsx(AlertDialogCancel, { children: "Cancel" }),
      /* @__PURE__ */ jsxs(
        AlertDialogAction,
        {
          className: "bg-destructive hover:bg-destructive/90 text-white",
          onClick: () => {
            onConfirm();
            onOpenChange(false);
          },
          children: [
            "Delete ",
            isMultiple ? "keys" : "key"
          ]
        }
      )
    ] })
  ] }) });
}
function CopyButton({ value }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(value).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2e3);
      },
      () => {
        console.error("Failed to copy key");
      }
    );
  };
  return /* @__PURE__ */ jsx(
    Button,
    {
      variant: "ghost",
      size: "icon",
      onClick: handleCopy,
      className: "size-8",
      title: "Copy key",
      children: copied ? /* @__PURE__ */ jsx(CircleCheck, { className: "size-4 text-green-500" }) : /* @__PURE__ */ jsx(Copy, { className: "size-4" })
    }
  );
}
function StatusBadge({ expirationDate }) {
  const daysRemaining = getDaysRemaining(expirationDate);
  const isExpired = daysRemaining < 0;
  const isExpiringSoon = daysRemaining >= 0 && daysRemaining <= 7;
  if (isExpired) {
    return /* @__PURE__ */ jsx(Badge, { className: "border-transparent bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400", children: "Expired" });
  }
  if (isExpiringSoon) {
    return /* @__PURE__ */ jsx(Badge, { className: "border-transparent bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400", children: "Expiring soon" });
  }
  return /* @__PURE__ */ jsx(Badge, { className: "border-transparent bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400", children: "Active" });
}
function ActionsDropdown({
  apiKey,
  onDelete
}) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsxs(DropdownMenu, { open: isOpen, onOpenChange: setIsOpen, children: [
      /* @__PURE__ */ jsx(DropdownMenuTrigger, { asChild: true, children: /* @__PURE__ */ jsxs(
        Button,
        {
          variant: "ghost",
          size: "icon",
          className: cn(
            "text-muted-foreground size-8 transition-opacity",
            isOpen ? "opacity-100" : "opacity-10 group-hover:opacity-50"
          ),
          onClick: (e) => e.stopPropagation(),
          children: [
            /* @__PURE__ */ jsx(Ellipsis, { className: "size-4" }),
            /* @__PURE__ */ jsx("span", { className: "sr-only", children: "Open menu" })
          ]
        }
      ) }),
      /* @__PURE__ */ jsxs(DropdownMenuContent, { align: "end", children: [
        /* @__PURE__ */ jsxs(
          DropdownMenuItem,
          {
            onClick: () => {
              navigator.clipboard.writeText(apiKey.id);
              toast.success("Copied to clipboard");
            },
            children: [
              /* @__PURE__ */ jsx(Copy, { className: "size-4" }),
              "Copy ID"
            ]
          }
        ),
        /* @__PURE__ */ jsxs(
          DropdownMenuItem,
          {
            onClick: () => {
              navigator.clipboard.writeText(JSON.stringify(apiKey, null, 2));
              toast.success("Copied to clipboard");
            },
            children: [
              /* @__PURE__ */ jsx(Braces, { className: "size-4" }),
              "Copy as JSON"
            ]
          }
        ),
        /* @__PURE__ */ jsxs(
          DropdownMenuItem,
          {
            variant: "destructive",
            onClick: () => setShowDeleteDialog(true),
            children: [
              /* @__PURE__ */ jsx(Trash2, { className: "size-4" }),
              "Delete"
            ]
          }
        )
      ] })
    ] }),
    /* @__PURE__ */ jsx(
      DeleteApiKeyDialog,
      {
        open: showDeleteDialog,
        onOpenChange: setShowDeleteDialog,
        keys: [apiKey],
        onConfirm: () => onDelete([apiKey.id])
      }
    )
  ] });
}
function ApiKeysTable({
  data,
  onDelete,
  selectedKey,
  onSelectKey,
  deleteDialogOpen,
  onDeleteDialogChange
}) {
  const [rowSelection, setRowSelection] = useState({});
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);
  const [keysToDelete, setKeysToDelete] = useState([]);
  const columns = useMemo(
    () => [
      getSelectionColumn(),
      {
        accessorKey: "decrypted_key",
        header: "Key",
        cell: ({ row }) => /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
          /* @__PURE__ */ jsx("code", { className: "font-mono text-xs font-medium", children: maskKey(row.original.decrypted_key) }),
          /* @__PURE__ */ jsx(CopyButton, { value: row.original.decrypted_key })
        ] }),
        filterFn: (row, _columnId, filterValue) => {
          const key = row.original.decrypted_key.toLowerCase();
          return key.startsWith(filterValue.toLowerCase());
        }
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => /* @__PURE__ */ jsx(StatusBadge, { expirationDate: row.original.expiration_date })
      },
      {
        accessorKey: "created_at",
        header: "Created",
        cell: ({ row }) => /* @__PURE__ */ jsx("span", { className: "text-muted-foreground text-sm", children: formatDate(row.original.created_at) })
      },
      {
        accessorKey: "expiration_date",
        header: "Expires",
        cell: ({ row }) => {
          const daysRemaining = getDaysRemaining(row.original.expiration_date);
          const isExpired = daysRemaining < 0;
          return /* @__PURE__ */ jsx("span", { className: `text-sm ${getStatusColor(daysRemaining)}`, children: isExpired ? `Expired ${Math.abs(daysRemaining)} day${Math.abs(daysRemaining) === 1 ? "" : "s"} ago` : `${daysRemaining} day${daysRemaining === 1 ? "" : "s"}` });
        }
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => /* @__PURE__ */ jsx("div", { className: "flex justify-end", children: /* @__PURE__ */ jsx(ActionsDropdown, { apiKey: row.original, onDelete }) })
      }
    ],
    [onDelete]
  );
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(
      DataTable,
      {
        columns,
        data,
        enableRowSelection: true,
        emptyMessage: "No API keys found.",
        getRowId: (row) => row.id,
        rowSelection,
        onRowSelectionChange: setRowSelection,
        highlightedRow: selectedKey,
        onRowHover: onSelectKey,
        renderFloatingToolbar: ({ selectedRows, table }) => {
          const selectedKeys = selectedRows.map((row) => row.original);
          return /* @__PURE__ */ jsx(
            DataTableFloatingToolbar,
            {
              selectedCount: selectedKeys.length,
              actions: [
                {
                  id: "copy-json",
                  label: "Export",
                  icon: Download,
                  onClick: () => {
                    navigator.clipboard.writeText(JSON.stringify(selectedKeys, null, 2)).then(() => {
                      toast.success(
                        `Copied ${selectedKeys.length} key${selectedKeys.length > 1 ? "s" : ""} as JSON`
                      );
                    });
                  }
                },
                {
                  id: "delete",
                  label: "Delete",
                  icon: Trash2,
                  variant: "destructive",
                  onClick: () => {
                    setKeysToDelete(selectedKeys);
                    setBulkDeleteDialogOpen(true);
                  }
                }
              ],
              onClearSelection: () => table.resetRowSelection()
            }
          );
        }
      }
    ),
    /* @__PURE__ */ jsx(
      DeleteApiKeyDialog,
      {
        open: bulkDeleteDialogOpen,
        onOpenChange: setBulkDeleteDialogOpen,
        keys: keysToDelete,
        onConfirm: () => {
          onDelete(keysToDelete.map((k) => k.id));
          setRowSelection({});
        }
      }
    ),
    selectedKey && /* @__PURE__ */ jsx(
      DeleteApiKeyDialog,
      {
        open: deleteDialogOpen,
        onOpenChange: onDeleteDialogChange,
        keys: [selectedKey],
        onConfirm: () => {
          onDelete([selectedKey.id]);
          onSelectKey(null);
        }
      }
    )
  ] });
}
function CreateApiKeyDialog({
  open,
  onOpenChange,
  orgId
}) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const createForm = useForm({
    defaultValues: {
      expirationDays: 90
    },
    onSubmit: async ({ value }) => {
      createMutation.mutate(value.expirationDays);
    }
  });
  const createMutation = useMutation({
    mutationFn: async (expirationDays) => {
      const token = await getAccessTokenSilently();
      return createApiKey(token, orgId, expirationDays);
    },
    onSuccess: (newKey) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.apiKeys.list(orgId)
      });
      onOpenChange(false);
      createForm.reset();
      navigator.clipboard.writeText(newKey.decrypted_key).then(
        () => {
          toast.success("API key created and copied to clipboard");
        },
        () => {
          toast.success("API key created", {
            description: "Failed to copy to clipboard automatically"
          });
        }
      );
    },
    onError: (error) => {
      const message = error.message || "Failed to create API key";
      const commaIndex = message.indexOf(", ");
      if (commaIndex > 0) {
        toast.error(message.substring(0, commaIndex), {
          description: message.substring(commaIndex + 2)
        });
      } else {
        toast.error("An error occurred", {
          description: message
        });
      }
    }
  });
  const handleClose = (newOpen) => {
    if (!newOpen) {
      createForm.reset();
    }
    onOpenChange(newOpen);
  };
  return /* @__PURE__ */ jsx(Dialog, { open, onOpenChange: handleClose, children: /* @__PURE__ */ jsxs(DialogContent, { className: "sm:max-w-md", children: [
    /* @__PURE__ */ jsxs(DialogHeader, { children: [
      /* @__PURE__ */ jsx(DialogTitle, { children: "Create API key" }),
      /* @__PURE__ */ jsx(DialogDescription, { children: "Choose how long this key should remain valid" })
    ] }),
    /* @__PURE__ */ jsx(
      "form",
      {
        onSubmit: (e) => {
          e.preventDefault();
          createForm.handleSubmit();
        },
        children: /* @__PURE__ */ jsx(createForm.Field, { name: "expirationDays", children: (field) => /* @__PURE__ */ jsxs(
          ApiForm,
          {
            method: "POST",
            endpoint: "https://api.airweave.ai/api-keys",
            body: { expiration_days: field.state.value },
            onBodyChange: (newBody) => field.handleChange(newBody.expiration_days || 90),
            children: [
              /* @__PURE__ */ jsx(ApiForm.Toggle, {}),
              /* @__PURE__ */ jsx(ApiForm.FormView, { className: "space-y-2", children: EXPIRATION_PRESETS.map((preset) => /* @__PURE__ */ jsxs(
                "button",
                {
                  type: "button",
                  onClick: () => field.handleChange(preset.days),
                  className: cn(
                    "flex w-full items-center justify-between rounded-lg border px-4 py-3.5 text-left transition-colors",
                    field.state.value === preset.days ? "border-primary bg-primary/5 dark:bg-primary/10" : "border-border hover:border-muted-foreground/25"
                  ),
                  children: [
                    /* @__PURE__ */ jsx(
                      "span",
                      {
                        className: cn(
                          "text-sm font-medium",
                          field.state.value === preset.days ? "text-foreground" : "text-muted-foreground"
                        ),
                        children: preset.label
                      }
                    ),
                    preset.recommended && /* @__PURE__ */ jsx("span", { className: "rounded-md bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-600 dark:text-blue-400", children: "Recommended" })
                  ]
                },
                preset.days
              )) }),
              /* @__PURE__ */ jsx(ApiForm.CodeView, { editable: true }),
              /* @__PURE__ */ jsxs(ApiForm.Footer, { children: [
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
                /* @__PURE__ */ jsx(Button, { type: "submit", disabled: createMutation.isPending, children: createMutation.isPending ? /* @__PURE__ */ jsxs(Fragment, { children: [
                  /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 size-4 animate-spin" }),
                  "Creating..."
                ] }) : "Create key" })
              ] })
            ]
          }
        ) })
      }
    )
  ] }) });
}
function ApiKeysDocs() {
  return /* @__PURE__ */ jsx(DocsContent, { docPath: "quickstart.mdx" });
}
function ApiKeysCode() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "Using API Keys" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Authenticate your requests with your API key:" }),
    /* @__PURE__ */ jsx("pre", { className: "bg-muted overflow-auto rounded-lg p-3 text-xs", children: /* @__PURE__ */ jsx("code", { children: `import { AirweaveSDK } from '@airweave/sdk';

const client = new AirweaveSDK({
  apiKey: 'YOUR_API_KEY',
  baseUrl: 'https://api.airweave.ai'
});

// Or use directly in headers
fetch('https://api.airweave.ai/collections', {
  headers: {
    'x-api-key': 'YOUR_API_KEY'
  }
});` }) })
  ] });
}
function ApiKeysHelp() {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
    /* @__PURE__ */ jsx("h3", { className: "text-base font-semibold", children: "API Key Security" }),
    /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Keep your API keys secure and never expose them in client-side code." }),
    /* @__PURE__ */ jsx("div", { className: "space-y-3", children: /* @__PURE__ */ jsxs("div", { className: "bg-muted rounded-lg p-3", children: [
      /* @__PURE__ */ jsx("h4", { className: "text-sm font-medium", children: "Best Practices" }),
      /* @__PURE__ */ jsxs("ul", { className: "text-muted-foreground mt-1 space-y-1 text-xs", children: [
        /* @__PURE__ */ jsx("li", { children: "Store keys in environment variables" }),
        /* @__PURE__ */ jsx("li", { children: "Rotate keys periodically" }),
        /* @__PURE__ */ jsx("li", { children: "Use different keys for dev/prod" })
      ] })
    ] }) })
  ] });
}
const PAGE_SIZE = 20;
function ApiKeysPage() {
  const {
    getAccessTokenSilently
  } = useAuth0();
  const {
    organization
  } = useOrg();
  const queryClient = useQueryClient();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedKeyId, setSelectedKeyId] = useState(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  if (!organization) {
    throw new Error("Organization context is required but not available");
  }
  const orgId = organization.id;
  const handleOpenCreateDialog = () => {
    setCreateDialogOpen(true);
  };
  usePageHeader({
    title: "API Keys",
    description: "Manage your API keys for programmatic access",
    actions: /* @__PURE__ */ jsxs(Button, { onClick: handleOpenCreateDialog, children: [
      /* @__PURE__ */ jsx(Plus, { className: "mr-2 size-4" }),
      "Create key"
    ] })
  });
  useRightSidebarContent({
    docs: /* @__PURE__ */ jsx(ApiKeysDocs, {}),
    code: /* @__PURE__ */ jsx(ApiKeysCode, {}),
    help: /* @__PURE__ */ jsx(ApiKeysHelp, {})
  });
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage
  } = useInfiniteQuery({
    queryKey: queryKeys.apiKeys.list(orgId),
    queryFn: async ({
      pageParam = 0
    }) => {
      const token = await getAccessTokenSilently();
      return fetchApiKeys(token, orgId, pageParam, PAGE_SIZE);
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage || !Array.isArray(lastPage)) {
        return void 0;
      }
      if (lastPage.length < PAGE_SIZE) {
        return void 0;
      }
      return allPages.flat().length;
    }
  });
  const deleteMutation = useMutation({
    mutationFn: async (keyIds) => {
      const token = await getAccessTokenSilently();
      await Promise.all(keyIds.map((id) => deleteApiKey(token, orgId, id)));
    },
    onMutate: async (keyIds) => {
      const listKey = queryKeys.apiKeys.list(orgId);
      await queryClient.cancelQueries({
        queryKey: listKey
      });
      const previousData = queryClient.getQueryData(listKey);
      const keyIdsSet = new Set(keyIds);
      queryClient.setQueryData(listKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          pages: old.pages.map((page) => page.filter((key) => !keyIdsSet.has(key.id)))
        };
      });
      return {
        previousData
      };
    },
    onError: (_err, _keyIds, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(queryKeys.apiKeys.list(orgId), context.previousData);
      }
    },
    onSuccess: (_data, keyIds) => {
      const count = keyIds.length;
      toast.success(count > 1 ? `${count} API keys deleted` : "API key deleted");
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.apiKeys.list(orgId)
      });
    }
  });
  const apiKeys = useMemo(() => data?.pages.flat() ?? [], [data?.pages]);
  const selectedKey = useMemo(() => {
    if (apiKeys.length === 0) return null;
    if (selectedKeyId) {
      const found = apiKeys.find((k) => k.id === selectedKeyId);
      if (found) return found;
    }
    return apiKeys[0];
  }, [apiKeys, selectedKeyId]);
  const contextCommands = useMemo(() => {
    if (!selectedKey) return [];
    const actions = getApiKeyActions({
      onCopyAsJson: () => {
        navigator.clipboard.writeText(JSON.stringify(selectedKey, null, 2));
        toast.success("Copied to clipboard");
      },
      onDelete: () => {
        setDeleteDialogOpen(true);
      }
    });
    return actions;
  }, [selectedKey]);
  useCommandMenu({
    pageTitle: "API Keys",
    pageCommands: [{
      id: "create-api-key",
      label: "Create API Key",
      icon: Plus,
      onSelect: handleOpenCreateDialog
    }],
    contextTitle: selectedKey ? maskKey(selectedKey.decrypted_key) : void 0,
    contextCommands
  });
  if (isLoading) {
    return /* @__PURE__ */ jsx("div", { className: "p-6", children: /* @__PURE__ */ jsx(LoadingState, {}) });
  }
  if (error) {
    return /* @__PURE__ */ jsx("div", { className: "p-6", children: /* @__PURE__ */ jsx(ErrorState, { error: error instanceof Error ? error : "Failed to load API keys" }) });
  }
  if (apiKeys.length === 0) {
    return /* @__PURE__ */ jsxs("div", { className: "p-6", children: [
      /* @__PURE__ */ jsx(EmptyState, { icon: /* @__PURE__ */ jsx(Key, {}), title: "No API keys yet", description: "Create your first key to start using the API programmatically.", children: /* @__PURE__ */ jsxs(Button, { variant: "outline", size: "sm", onClick: handleOpenCreateDialog, children: [
        /* @__PURE__ */ jsx(Plus, { className: "mr-2 size-4" }),
        "Create key"
      ] }) }),
      /* @__PURE__ */ jsx(CreateApiKeyDialog, { open: createDialogOpen, onOpenChange: setCreateDialogOpen, orgId })
    ] });
  }
  return /* @__PURE__ */ jsxs("div", { children: [
    /* @__PURE__ */ jsx(ApiKeysTable, { data: apiKeys, onDelete: (ids) => deleteMutation.mutate(ids), selectedKey, onSelectKey: (key) => setSelectedKeyId(key?.id ?? null), deleteDialogOpen, onDeleteDialogChange: setDeleteDialogOpen }),
    hasNextPage && /* @__PURE__ */ jsx("div", { className: "flex justify-center pt-4", children: /* @__PURE__ */ jsx(Button, { variant: "outline", onClick: () => fetchNextPage(), disabled: isFetchingNextPage, children: isFetchingNextPage ? /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 size-4 animate-spin" }),
      "Loading..."
    ] }) : "Load more" }) }),
    /* @__PURE__ */ jsx(CreateApiKeyDialog, { open: createDialogOpen, onOpenChange: setCreateDialogOpen, orgId })
  ] });
}
export {
  ApiKeysPage as component
};
