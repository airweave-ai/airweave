import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import { useQueryClient, useInfiniteQuery, useQuery, useMutation } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { toast } from "sonner";
import { u as useAuth0, j as useCreateCollectionStore, a9 as usePageHeader, aa as useRightSidebarContent, q as queryKeys, B as Button, P as Plus, al as LayoutGrid, L as LoaderCircle, a as cn, E as DropdownMenu, F as DropdownMenuTrigger, G as DropdownMenuContent, K as DropdownMenuItem, a6 as Avatar, a7 as AvatarImage, a8 as AvatarFallback } from "./router-BGxBdlkD.mjs";
import { E as EmptyState } from "./empty-state-BldPO3ai.mjs";
import { E as ErrorState, C as Copy, A as AlertDialog, b as AlertDialogContent, c as AlertDialogHeader, d as AlertDialogTitle, e as AlertDialogDescription, f as AlertDialogFooter, g as AlertDialogCancel, h as AlertDialogAction } from "./error-state-BYmPP-hR.mjs";
import { L as LoadingState } from "./loading-state-CJE8ekwd.mjs";
import { f as fetchCollections, d as deleteCollection } from "./collections-Bp-yOdLv.mjs";
import { u as useIsDark } from "./use-is-dark-CmoXbbju.mjs";
import { f as fetchSources, a as formatDate, g as getCollectionStatusDisplay, b as getAppIconUrl, C as CollectionsHelp, c as CollectionsCode, d as CollectionsDocs } from "./sidebar-content-DdEgH4En.mjs";
import { u as useOrg } from "./org-context-BXR7_uGh.mjs";
import { B as Badge } from "./badge-B1TPqLQ8.mjs";
import { g as getSelectionColumn, D as DataTable, a as DataTableFloatingToolbar, b as Download, E as Ellipsis, B as Braces } from "./data-table-floating-toolbar-BlF-76To.mjs";
import { T as Trash2 } from "./trash-2.mjs";
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
import "./use-docs-content-CQG4H0bA.mjs";
import "./checkbox-L51m4-da.mjs";
import "@radix-ui/react-checkbox";
import "@tanstack/react-table";
function BulkDeleteCollectionsDialog({
  open,
  onOpenChange,
  collections,
  onConfirm
}) {
  const count = collections.length;
  const isMultiple = count > 1;
  if (count === 0) return null;
  return /* @__PURE__ */ jsx(AlertDialog, { open, onOpenChange, children: /* @__PURE__ */ jsxs(AlertDialogContent, { className: "sm:max-w-md", children: [
    /* @__PURE__ */ jsxs(AlertDialogHeader, { children: [
      /* @__PURE__ */ jsxs(AlertDialogTitle, { children: [
        "Delete ",
        isMultiple ? `${count} collections` : "collection"
      ] }),
      /* @__PURE__ */ jsxs(AlertDialogDescription, { children: [
        "This action cannot be undone.",
        " ",
        isMultiple ? "These collections" : "This collection",
        " and all associated source connections, synced data, and configuration will be permanently deleted."
      ] })
    ] }),
    /* @__PURE__ */ jsx(
      "div",
      {
        className: `bg-muted my-4 rounded-lg border p-3 ${isMultiple ? "max-h-32 space-y-1 overflow-y-auto" : ""}`,
        children: collections.map((collection) => /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
          /* @__PURE__ */ jsx("span", { className: "font-medium", children: collection.name }),
          /* @__PURE__ */ jsxs("code", { className: "text-muted-foreground font-mono text-xs", children: [
            collection.readable_id,
            ".airweave.ai"
          ] })
        ] }, collection.id))
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
            isMultiple ? "collections" : "collection"
          ]
        }
      )
    ] })
  ] }) });
}
function StatusBadge({ status }) {
  const statusDisplay = getCollectionStatusDisplay(status);
  return /* @__PURE__ */ jsx(
    Badge,
    {
      variant: statusDisplay.variant === "success" ? "default" : statusDisplay.variant === "warning" ? "secondary" : statusDisplay.variant === "destructive" ? "destructive" : "outline",
      className: cn(
        "w-fit",
        statusDisplay.variant === "success" && "border-transparent bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
        statusDisplay.variant === "warning" && "border-transparent bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
      ),
      children: statusDisplay.label
    }
  );
}
function ActionsDropdown({
  collection,
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
              navigator.clipboard.writeText(collection.id);
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
              navigator.clipboard.writeText(
                JSON.stringify(collection, null, 2)
              );
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
      BulkDeleteCollectionsDialog,
      {
        open: showDeleteDialog,
        onOpenChange: setShowDeleteDialog,
        collections: [collection],
        onConfirm: () => onDelete([collection.readable_id])
      }
    )
  ] });
}
function CollectionsTable({
  data,
  onDelete,
  onRowClick,
  selectedCollection,
  onSelectCollection,
  deleteDialogOpen,
  onDeleteDialogChange
}) {
  const [rowSelection, setRowSelection] = useState({});
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);
  const [collectionsToDelete, setCollectionsToDelete] = useState(
    []
  );
  const columns = useMemo(
    () => [
      getSelectionColumn(),
      {
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) => /* @__PURE__ */ jsx("span", { className: "font-medium", children: row.original.name })
      },
      {
        accessorKey: "readable_id",
        header: "Domain",
        cell: ({ row }) => /* @__PURE__ */ jsxs("code", { className: "text-muted-foreground font-mono text-xs", children: [
          row.original.readable_id,
          ".airweave.ai"
        ] })
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => /* @__PURE__ */ jsx(StatusBadge, { status: row.original.status })
      },
      {
        accessorKey: "created_at",
        header: "Created",
        cell: ({ row }) => /* @__PURE__ */ jsx("span", { className: "text-muted-foreground text-sm", children: formatDate(row.original.created_at) })
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => /* @__PURE__ */ jsx("div", { className: "flex justify-end", children: /* @__PURE__ */ jsx(ActionsDropdown, { collection: row.original, onDelete }) })
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
        emptyMessage: "No collections found.",
        getRowId: (row) => row.id,
        rowSelection,
        onRowSelectionChange: setRowSelection,
        highlightedRow: selectedCollection,
        onRowHover: onSelectCollection,
        onRowClick,
        renderFloatingToolbar: ({ selectedRows, table }) => {
          const selectedCollections = selectedRows.map((row) => row.original);
          return /* @__PURE__ */ jsx(
            DataTableFloatingToolbar,
            {
              selectedCount: selectedCollections.length,
              actions: [
                {
                  id: "copy-json",
                  label: "Export",
                  icon: Download,
                  onClick: () => {
                    navigator.clipboard.writeText(JSON.stringify(selectedCollections, null, 2)).then(() => {
                      toast.success(
                        `Copied ${selectedCollections.length} collection${selectedCollections.length > 1 ? "s" : ""} as JSON`
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
                    setCollectionsToDelete(selectedCollections);
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
      BulkDeleteCollectionsDialog,
      {
        open: bulkDeleteDialogOpen,
        onOpenChange: setBulkDeleteDialogOpen,
        collections: collectionsToDelete,
        onConfirm: () => {
          onDelete(collectionsToDelete.map((c) => c.readable_id));
          setRowSelection({});
        }
      }
    ),
    selectedCollection && /* @__PURE__ */ jsx(
      BulkDeleteCollectionsDialog,
      {
        open: deleteDialogOpen,
        onOpenChange: onDeleteDialogChange,
        collections: [selectedCollection],
        onConfirm: () => {
          onDelete([selectedCollection.readable_id]);
          onSelectCollection(null);
        }
      }
    )
  ] });
}
function SourceCard({
  name,
  shortName,
  onClick,
  disabled = false
}) {
  const isDark = useIsDark();
  return /* @__PURE__ */ jsxs(
    "div",
    {
      className: cn(
        "group border-border/50 flex items-center justify-center gap-2 overflow-hidden rounded-lg border px-3 py-1.5 shadow-xs transition-all",
        disabled ? "bg-card/50 cursor-not-allowed opacity-50" : "bg-card hover:bg-card/50 hover:border-border cursor-pointer"
      ),
      onClick: disabled ? void 0 : onClick,
      children: [
        /* @__PURE__ */ jsx(SourceIcon, { shortName, isDark }),
        /* @__PURE__ */ jsx(
          "div",
          {
            className: cn(
              "truncate text-xs font-medium",
              disabled && "text-muted-foreground"
            ),
            children: name
          }
        )
      ]
    }
  );
}
function SourceIcon({ shortName, isDark }) {
  return /* @__PURE__ */ jsxs(Avatar, { className: "size-6 rounded", children: [
    /* @__PURE__ */ jsx(
      AvatarImage,
      {
        src: getAppIconUrl(shortName, isDark ? "dark" : "light"),
        alt: `${shortName} icon`
      }
    ),
    /* @__PURE__ */ jsx(AvatarFallback, { className: "rounded text-xs font-semibold", children: shortName[0].toUpperCase() })
  ] });
}
function SourcesGrid({
  sources,
  onSourceClick,
  title = "Start with a source"
}) {
  if (sources.length === 0) {
    return null;
  }
  return /* @__PURE__ */ jsxs("div", { children: [
    /* @__PURE__ */ jsx("h2", { className: "text-muted-foreground mb-4 font-mono font-medium uppercase opacity-70", children: title }),
    /* @__PURE__ */ jsx("div", { className: "flex flex-wrap gap-3", children: sources.map((source) => /* @__PURE__ */ jsx(
      SourceCard,
      {
        id: source.id,
        name: source.name,
        shortName: source.short_name,
        onClick: () => onSourceClick(source)
      },
      source.id
    )) })
  ] });
}
const PAGE_SIZE = 24;
function CollectionsPage() {
  const navigate = useNavigate();
  const {
    getAccessTokenSilently
  } = useAuth0();
  const {
    organization,
    getOrgSlug
  } = useOrg();
  const queryClient = useQueryClient();
  const openCreateCollection = useCreateCollectionStore((s) => s.open);
  const openWithSource = useCreateCollectionStore((s) => s.openWithSource);
  const [selectedCollectionId, setSelectedCollectionId] = useState(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  if (!organization) {
    throw new Error("Organization context is required but not available");
  }
  const orgId = organization.id;
  const orgSlug = getOrgSlug(organization);
  usePageHeader({
    title: "Collections",
    description: "Manage your searchable knowledge bases",
    actions: /* @__PURE__ */ jsxs(Button, { onClick: openCreateCollection, children: [
      /* @__PURE__ */ jsx(Plus, { className: "mr-2 size-4" }),
      "Create Collection"
    ] })
  });
  useRightSidebarContent({
    docs: /* @__PURE__ */ jsx(CollectionsDocs, {}),
    code: /* @__PURE__ */ jsx(CollectionsCode, {}),
    help: /* @__PURE__ */ jsx(CollectionsHelp, {})
  });
  const {
    data: collectionsData,
    isLoading: isLoadingCollections,
    error: collectionsError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage
  } = useInfiniteQuery({
    queryKey: queryKeys.collections.list(orgId),
    queryFn: async ({
      pageParam = 0
    }) => {
      const token = await getAccessTokenSilently();
      return fetchCollections(token, orgId, pageParam, PAGE_SIZE);
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
  const {
    data: sources,
    isLoading: isLoadingSources,
    error: sourcesError
  } = useQuery({
    queryKey: queryKeys.sources.list(orgId),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSources(token, orgId);
    }
  });
  const deleteMutation = useMutation({
    mutationFn: async (readableIds) => {
      const token = await getAccessTokenSilently();
      await Promise.all(readableIds.map((readableId) => deleteCollection(token, orgId, readableId)));
    },
    onMutate: async (readableIds) => {
      const listKey = queryKeys.collections.list(orgId);
      await queryClient.cancelQueries({
        queryKey: listKey
      });
      const previousData = queryClient.getQueryData(listKey);
      const readableIdsSet = new Set(readableIds);
      queryClient.setQueryData(listKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          pages: old.pages.map((page) => page.filter((collection) => !readableIdsSet.has(collection.readable_id)))
        };
      });
      return {
        previousData
      };
    },
    onError: (_err, _readableIds, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(queryKeys.collections.list(orgId), context.previousData);
      }
    },
    onSuccess: (_data, readableIds) => {
      const count = readableIds.length;
      toast.success(count > 1 ? `${count} collections deleted` : "Collection deleted");
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.collections.list(orgId)
      });
    }
  });
  const collections = useMemo(() => collectionsData?.pages.flat() ?? [], [collectionsData?.pages]);
  const selectedCollection = useMemo(() => {
    if (collections.length === 0) return null;
    if (selectedCollectionId) {
      const found = collections.find((c) => c.id === selectedCollectionId);
      if (found) return found;
    }
    return collections[0];
  }, [collections, selectedCollectionId]);
  const sortedSources = useMemo(() => {
    if (!sources) return [];
    return [...sources].sort((a, b) => a.name.localeCompare(b.name));
  }, [sources]);
  const handleSourceClick = (source) => {
    openWithSource(source.short_name, source.name);
  };
  const handleCollectionClick = (collection) => {
    navigate({
      to: `/${orgSlug}/collections/${collection.readable_id}`
    });
  };
  const isLoading = isLoadingCollections || isLoadingSources;
  const error = collectionsError || sourcesError;
  if (isLoading && collections.length === 0) {
    return /* @__PURE__ */ jsx("div", { className: "p-6", children: /* @__PURE__ */ jsx(LoadingState, {}) });
  }
  if (error) {
    return /* @__PURE__ */ jsx("div", { className: "p-6", children: /* @__PURE__ */ jsx(ErrorState, { error: error instanceof Error ? error : "Failed to load collections" }) });
  }
  if (collections.length === 0 && !isLoadingCollections) {
    return /* @__PURE__ */ jsxs("div", { className: "space-y-8 p-6", children: [
      /* @__PURE__ */ jsx(EmptyState, { icon: /* @__PURE__ */ jsx(LayoutGrid, {}), title: "Create your first collection", description: "Collections help you organize and search your data from multiple sources.", children: /* @__PURE__ */ jsxs(Button, { variant: "outline", onClick: openCreateCollection, children: [
        /* @__PURE__ */ jsx(Plus, { className: "mr-2 size-4" }),
        "Create Collection"
      ] }) }),
      /* @__PURE__ */ jsx(SourcesGrid, { sources: sortedSources, onSourceClick: handleSourceClick })
    ] });
  }
  return /* @__PURE__ */ jsxs("div", { className: "space-y-8", children: [
    /* @__PURE__ */ jsx(CollectionsTable, { data: collections, onDelete: (readableIds) => deleteMutation.mutate(readableIds), onRowClick: handleCollectionClick, selectedCollection, onSelectCollection: (collection) => setSelectedCollectionId(collection?.id ?? null), deleteDialogOpen, onDeleteDialogChange: setDeleteDialogOpen }),
    hasNextPage && /* @__PURE__ */ jsx("div", { className: "flex justify-center", children: /* @__PURE__ */ jsx(Button, { variant: "outline", onClick: () => fetchNextPage(), disabled: isFetchingNextPage, children: isFetchingNextPage ? /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 size-4 animate-spin" }),
      "Loading..."
    ] }) : "Load more" }) }),
    /* @__PURE__ */ jsx("div", { className: "px-6 pb-6", children: /* @__PURE__ */ jsx(SourcesGrid, { sources: sortedSources, onSourceClick: handleSourceClick }) })
  ] });
}
export {
  CollectionsPage as component
};
