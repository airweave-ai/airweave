import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import { Outlet, useNavigate } from "@tanstack/react-router";
import { useRef, useEffect, useState } from "react";
import { c as createCollection } from "./collections-Bp-yOdLv.mjs";
import { toast } from "sonner";
import { u as useAuth0, j as useCreateCollectionStore, q as queryKeys, D as Dialog, k as DialogContent, l as DialogHeader, m as DialogTitle, n as DialogDescription, a as cn, B as Button, L as LoaderCircle } from "./router-BGxBdlkD.mjs";
import { O as OrgProvider, u as useOrg } from "./org-context-BXR7_uGh.mjs";
import { useForm } from "@tanstack/react-form";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { A as ApiForm } from "./api-form-BOZocKEu.mjs";
import { I as Input } from "./input-CQnbKF5R.mjs";
import { L as LoadingState } from "./loading-state-CJE8ekwd.mjs";
import { f as fetchApiKeys } from "./api-keys-DlD7J9DW.mjs";
import { f as fetchAuthProviders, a as fetchAuthProviderConnections } from "./auth-providers-Djkzae2F.mjs";
import "zustand";
import "zustand/middleware";
import "@tanstack/react-query-persist-client";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "clsx";
import "tailwind-merge";
import "@radix-ui/react-dialog";
import "@radix-ui/react-tooltip";
import "@radix-ui/react-avatar";
import "@radix-ui/react-dropdown-menu";
import "cmdk";
import "idb-keyval";
import "./tabs-ChSqzczQ.mjs";
import "@radix-ui/react-tabs";
function generateRandomSuffix(length = 6) {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}
function generateReadableId(name, suffix) {
  if (!name.trim()) return "";
  let readableId = name.toLowerCase().trim();
  readableId = readableId.replace(/[^a-z0-9\s]/g, "");
  readableId = readableId.replace(/\s+/g, "-");
  readableId = readableId.replace(/-+/g, "-");
  readableId = readableId.replace(/^-+|-+$/g, "");
  return readableId ? `${readableId}-${suffix}` : "";
}
function CreateCollectionDialog({
  open,
  onOpenChange,
  orgId,
  onSuccess
}) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const [randomSuffix, setRandomSuffix] = useState(generateRandomSuffix);
  const [userEditedId, setUserEditedId] = useState(false);
  const [currentName, setCurrentName] = useState("");
  const [currentReadableId, setCurrentReadableId] = useState("");
  useEffect(() => {
    if (open) {
      setRandomSuffix(generateRandomSuffix());
    }
  }, [open]);
  const form = useForm({
    defaultValues: {
      name: "",
      readableId: ""
    },
    onSubmit: async ({ value }) => {
      createMutation.mutate(value);
    }
  });
  const createMutation = useMutation({
    mutationFn: async (values) => {
      const token = await getAccessTokenSilently();
      return createCollection(token, orgId, {
        name: values.name,
        readable_id: values.readableId || void 0
      });
    },
    onSuccess: (collection) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.collections.all(orgId)
      });
      toast.success(`Collection "${collection.name}" created!`, {
        description: `ID: ${collection.readable_id}`
      });
      onOpenChange(false);
      form.reset();
      setUserEditedId(false);
      setCurrentName("");
      setCurrentReadableId("");
      onSuccess?.(collection);
    },
    onError: (error) => {
      const message = error.message || "Failed to create collection";
      const commaIndex = message.indexOf(", ");
      if (commaIndex > 0) {
        toast.error(message.substring(0, commaIndex), {
          description: message.substring(commaIndex + 2)
        });
      } else {
        toast.error("Failed to create collection", {
          description: message
        });
      }
    }
  });
  const handleClose = (newOpen) => {
    if (!newOpen) {
      form.reset();
      setUserEditedId(false);
      setCurrentName("");
      setCurrentReadableId("");
    }
    onOpenChange(newOpen);
  };
  const displayReadableId = userEditedId ? currentReadableId : generateReadableId(currentName, randomSuffix);
  return /* @__PURE__ */ jsx(Dialog, { open, onOpenChange: handleClose, children: /* @__PURE__ */ jsxs(DialogContent, { className: "sm:max-w-md", children: [
    /* @__PURE__ */ jsxs(DialogHeader, { children: [
      /* @__PURE__ */ jsx(DialogTitle, { children: "Create collection" }),
      /* @__PURE__ */ jsx(DialogDescription, { children: "Collections are searchable knowledge bases for your data" })
    ] }),
    /* @__PURE__ */ jsx(
      "form",
      {
        onSubmit: (e) => {
          e.preventDefault();
          if (!userEditedId && displayReadableId) {
            form.setFieldValue("readableId", displayReadableId);
          }
          form.handleSubmit();
        },
        children: /* @__PURE__ */ jsxs(
          ApiForm,
          {
            method: "POST",
            endpoint: "https://api.airweave.ai/collections",
            body: {
              name: currentName,
              ...displayReadableId && { readable_id: displayReadableId }
            },
            onBodyChange: (newBody) => {
              if (typeof newBody.name === "string") {
                form.setFieldValue("name", newBody.name);
                setCurrentName(newBody.name);
              }
              if (typeof newBody.readable_id === "string") {
                form.setFieldValue("readableId", newBody.readable_id);
                setCurrentReadableId(newBody.readable_id);
                setUserEditedId(true);
              }
            },
            children: [
              /* @__PURE__ */ jsx(ApiForm.Toggle, {}),
              /* @__PURE__ */ jsxs(ApiForm.FormView, { className: "space-y-4", children: [
                /* @__PURE__ */ jsx(
                  form.Field,
                  {
                    name: "name",
                    validators: {
                      onChange: ({ value }) => {
                        if (!value.trim()) return "Name is required";
                        if (value.length < 4)
                          return "Name must be at least 4 characters";
                        if (value.length > 64)
                          return "Name must be less than 64 characters";
                        return void 0;
                      }
                    },
                    children: (field) => /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
                      /* @__PURE__ */ jsx(
                        "label",
                        {
                          htmlFor: "name",
                          className: "text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
                          children: "Name"
                        }
                      ),
                      /* @__PURE__ */ jsx(
                        Input,
                        {
                          id: "name",
                          placeholder: "e.g., Customer Support Tickets",
                          value: field.state.value,
                          onChange: (e) => {
                            field.handleChange(e.target.value);
                            setCurrentName(e.target.value);
                          },
                          onBlur: field.handleBlur,
                          "aria-invalid": field.state.meta.errors.length > 0 ? "true" : void 0
                        }
                      ),
                      field.state.meta.errors.length > 0 && /* @__PURE__ */ jsx("p", { className: "text-destructive text-sm", children: field.state.meta.errors[0] }),
                      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-xs", children: "4-64 characters. This is the display name for your collection." })
                    ] })
                  }
                ),
                /* @__PURE__ */ jsx(form.Field, { name: "readableId", children: (field) => /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
                  /* @__PURE__ */ jsxs(
                    "label",
                    {
                      htmlFor: "readableId",
                      className: "text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
                      children: [
                        "ID",
                        " ",
                        /* @__PURE__ */ jsx("span", { className: "text-muted-foreground font-normal", children: "(optional)" })
                      ]
                    }
                  ),
                  /* @__PURE__ */ jsx(
                    Input,
                    {
                      id: "readableId",
                      placeholder: "Auto-generated from name",
                      value: userEditedId ? field.state.value : "",
                      onChange: (e) => {
                        field.handleChange(e.target.value);
                        setCurrentReadableId(e.target.value);
                        setUserEditedId(true);
                      },
                      onBlur: field.handleBlur
                    }
                  ),
                  displayReadableId && /* @__PURE__ */ jsxs("p", { className: "text-muted-foreground text-xs", children: [
                    userEditedId ? "Custom ID: " : "Generated ID: ",
                    /* @__PURE__ */ jsx(
                      "code",
                      {
                        className: cn(
                          "rounded px-1 py-0.5",
                          "bg-muted font-mono text-xs"
                        ),
                        children: displayReadableId
                      }
                    )
                  ] })
                ] }) })
              ] }),
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
                /* @__PURE__ */ jsx(
                  Button,
                  {
                    type: "submit",
                    disabled: createMutation.isPending || !currentName.trim(),
                    children: createMutation.isPending ? /* @__PURE__ */ jsxs(Fragment, { children: [
                      /* @__PURE__ */ jsx(LoaderCircle, { className: "mr-2 size-4 animate-spin" }),
                      "Creating..."
                    ] }) : "Create collection"
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
function GlobalDialogs() {
  const navigate = useNavigate();
  const { organization, getOrgSlug } = useOrg();
  const {
    isOpen: isCreateOpen,
    close: closeCreate,
    preSelectedSource
  } = useCreateCollectionStore();
  const clearPreSelectedSource = useCreateCollectionStore(
    (s) => s.clearPreSelectedSource
  );
  if (!organization) return null;
  const orgSlug = getOrgSlug(organization);
  const handleCollectionCreated = (collection) => {
    const sourceToAdd = preSelectedSource;
    clearPreSelectedSource();
    const state = sourceToAdd ? { addSource: sourceToAdd } : void 0;
    navigate({
      to: `/${orgSlug}/collections/${collection.readable_id}`,
      state
    });
  };
  return /* @__PURE__ */ jsx(
    CreateCollectionDialog,
    {
      open: isCreateOpen,
      onOpenChange: (open) => {
        if (!open) closeCreate();
      },
      orgId: organization.id,
      onSuccess: handleCollectionCreated
    }
  );
}
const API_KEYS_PAGE_SIZE = 20;
function OrgDataPreloader() {
  const { organization } = useOrg();
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const lastPrefetchedOrgId = useRef(null);
  useEffect(() => {
    if (!organization?.id) return;
    const orgId = organization.id;
    if (lastPrefetchedOrgId.current === orgId) return;
    lastPrefetchedOrgId.current = orgId;
    const prefetchData = async () => {
      try {
        const token = await getAccessTokenSilently();
        queryClient.prefetchInfiniteQuery({
          queryKey: queryKeys.apiKeys.list(orgId),
          queryFn: ({ pageParam = 0 }) => fetchApiKeys(token, orgId, pageParam, API_KEYS_PAGE_SIZE),
          initialPageParam: 0,
          getNextPageParam: (lastPage, allPages) => {
            if (!lastPage || lastPage.length < API_KEYS_PAGE_SIZE)
              return void 0;
            return allPages.flat().length;
          },
          staleTime: 1e3 * 60 * 5
        });
        queryClient.prefetchQuery({
          queryKey: queryKeys.authProviders.list(orgId),
          queryFn: () => fetchAuthProviders(token, orgId),
          staleTime: 1e3 * 60 * 5
        });
        queryClient.prefetchQuery({
          queryKey: queryKeys.authProviders.connections(orgId),
          queryFn: () => fetchAuthProviderConnections(token, orgId),
          staleTime: 1e3 * 60 * 5
        });
      } catch (error) {
        console.debug("Org data prefetch failed:", error);
      }
    };
    prefetchData();
  }, [organization?.id, getAccessTokenSilently, queryClient]);
  return null;
}
function OrgLayout() {
  return /* @__PURE__ */ jsx(OrgProvider, { children: /* @__PURE__ */ jsx(OrgLayoutContent, {}) });
}
function OrgLayoutContent() {
  const {
    organization,
    isLoading
  } = useOrg();
  if (isLoading || !organization) {
    return /* @__PURE__ */ jsx("div", { className: "flex h-full items-center justify-center p-6", children: /* @__PURE__ */ jsx(LoadingState, {}) });
  }
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(OrgDataPreloader, {}),
    /* @__PURE__ */ jsx(Outlet, {}),
    /* @__PURE__ */ jsx(GlobalDialogs, {})
  ] });
}
export {
  OrgLayout as component
};
