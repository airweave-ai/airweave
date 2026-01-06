import { create } from "zustand";
import { persist } from "zustand/middleware";
import { jsx } from "react/jsx-runtime";
import * as React from "react";
import { af as API_BASE_URL, ag as getAuthHeaders, ah as parseErrorResponse, a as cn } from "./router-BGxBdlkD.mjs";
const initialState = {
  isOpen: false,
  currentStep: "source-select",
  collectionId: null,
  collectionName: null,
  selectedSourceShortName: null,
  selectedSourceName: null,
  connectionName: "",
  authMode: null,
  authFields: {},
  configFields: {},
  useCustomOAuth: false,
  clientId: "",
  clientSecret: "",
  customRedirectUrl: "",
  selectedAuthProviderId: null,
  authProviderConfig: {},
  oauthUrl: null,
  createdConnectionId: null
};
const useAddSourceStore = create()(
  persist(
    (set, get) => ({
      ...initialState,
      open: (collectionId, collectionName, preSelectedSource) => {
        if (preSelectedSource) {
          set({
            ...initialState,
            isOpen: true,
            currentStep: "source-config",
            collectionId,
            collectionName,
            selectedSourceShortName: preSelectedSource.shortName,
            selectedSourceName: preSelectedSource.name,
            connectionName: `${preSelectedSource.name} Connection`
          });
        } else {
          set({
            ...initialState,
            isOpen: true,
            currentStep: "source-select",
            collectionId,
            collectionName
          });
        }
      },
      close: () => {
        set({ isOpen: false });
      },
      reset: () => {
        set(initialState);
      },
      setStep: (step) => {
        set({ currentStep: step });
      },
      goBack: () => {
        const { currentStep } = get();
        switch (currentStep) {
          case "source-config":
            set({ currentStep: "source-select" });
            break;
          case "oauth-pending":
            set({ currentStep: "source-config" });
            break;
        }
      },
      selectSource: (shortName, displayName) => {
        set({
          selectedSourceShortName: shortName,
          selectedSourceName: displayName,
          connectionName: `${displayName} Connection`,
          currentStep: "source-config",
          authMode: null,
          authFields: {},
          configFields: {},
          useCustomOAuth: false,
          clientId: "",
          clientSecret: "",
          customRedirectUrl: "",
          selectedAuthProviderId: null,
          authProviderConfig: {}
        });
      },
      clearSource: () => {
        set({
          selectedSourceShortName: null,
          selectedSourceName: null,
          connectionName: "",
          authMode: null,
          authFields: {},
          configFields: {}
        });
      },
      setConnectionName: (name) => {
        set({ connectionName: name });
      },
      setAuthMode: (mode) => {
        set({
          authMode: mode,
          authFields: {},
          useCustomOAuth: false,
          clientId: "",
          clientSecret: "",
          selectedAuthProviderId: null,
          authProviderConfig: {}
        });
      },
      setAuthField: (name, value) => {
        set((state) => ({
          authFields: { ...state.authFields, [name]: value }
        }));
      },
      setAuthFields: (fields) => {
        set({ authFields: fields });
      },
      setConfigField: (name, value) => {
        set((state) => ({
          configFields: { ...state.configFields, [name]: value }
        }));
      },
      setConfigFields: (fields) => {
        set({ configFields: fields });
      },
      setUseCustomOAuth: (use) => {
        set({ useCustomOAuth: use });
      },
      setClientId: (id) => {
        set({ clientId: id });
      },
      setClientSecret: (secret) => {
        set({ clientSecret: secret });
      },
      setCustomRedirectUrl: (url) => {
        set({ customRedirectUrl: url });
      },
      setSelectedAuthProviderId: (id) => {
        set({
          selectedAuthProviderId: id,
          authProviderConfig: {}
        });
      },
      setAuthProviderConfig: (config) => {
        set({ authProviderConfig: config });
      },
      setOAuthUrl: (url) => {
        set({ oauthUrl: url });
      },
      setCreatedConnectionId: (id) => {
        set({ createdConnectionId: id });
      },
      completeWithOAuth: (connectionId, oauthUrl) => {
        set({
          createdConnectionId: connectionId,
          oauthUrl,
          currentStep: "oauth-pending"
        });
      },
      completeWithoutOAuth: (connectionId) => {
        set({
          createdConnectionId: connectionId,
          currentStep: "success"
        });
      }
    }),
    {
      name: "add-source-storage",
      // Only persist essential OAuth flow state for redirect handling
      partialize: (state) => ({
        collectionId: state.collectionId,
        collectionName: state.collectionName,
        selectedSourceShortName: state.selectedSourceShortName,
        selectedSourceName: state.selectedSourceName,
        connectionName: state.connectionName,
        createdConnectionId: state.createdConnectionId,
        oauthUrl: state.oauthUrl
      })
    }
  )
);
const Label = React.forwardRef(
  ({ className, ...props }, ref) => /* @__PURE__ */ jsx(
    "label",
    {
      ref,
      className: cn(
        "text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
        className
      ),
      ...props
    }
  )
);
Label.displayName = "Label";
async function fetchCollections(token, orgId, skip = 0, limit = 100, search) {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString()
  });
  const response = await fetch(`${API_BASE_URL}/collections?${params}`, {
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch collections"
    );
    throw new Error(message);
  }
  return response.json();
}
async function fetchCollection(token, orgId, readableId) {
  const response = await fetch(`${API_BASE_URL}/collections/${readableId}`, {
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch collection"
    );
    throw new Error(message);
  }
  return response.json();
}
async function createCollection(token, orgId, data) {
  const response = await fetch(`${API_BASE_URL}/collections`, {
    method: "POST",
    headers: getAuthHeaders(token, orgId),
    body: JSON.stringify(data)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create collection"
    );
    throw new Error(message);
  }
  return response.json();
}
async function deleteCollection(token, orgId, readableId) {
  const response = await fetch(`${API_BASE_URL}/collections/${readableId}`, {
    method: "DELETE",
    headers: getAuthHeaders(token, orgId)
  });
  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to delete collection"
    );
    throw new Error(message);
  }
  return response.json();
}
export {
  Label as L,
  fetchCollection as a,
  createCollection as c,
  deleteCollection as d,
  fetchCollections as f,
  useAddSourceStore as u
};
