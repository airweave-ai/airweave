/**
 * Store for managing the "Add Source to Collection" flow.
 *
 * Steps: source-select → source-config → oauth-pending (if needed) → success
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type AddSourceStep =
  | "source-select"
  | "source-config"
  | "oauth-pending"
  | "success";

export type AuthMode = "oauth2" | "direct_auth" | "external_provider";

interface AddSourceState {
  isOpen: boolean;
  currentStep: AddSourceStep;

  collectionId: string | null;
  collectionName: string | null;

  selectedSourceShortName: string | null;
  selectedSourceName: string | null;

  connectionName: string;
  authMode: AuthMode | null;
  authFields: Record<string, string>;
  configFields: Record<string, string | string[]>;

  useCustomOAuth: boolean;
  clientId: string;
  clientSecret: string;
  customRedirectUrl: string;

  selectedAuthProviderId: string | null;
  authProviderConfig: Record<string, string>;

  oauthUrl: string | null;
  createdConnectionId: string | null;

  open: (
    collectionId: string,
    collectionName: string,
    preSelectedSource?: { shortName: string; name: string }
  ) => void;
  close: () => void;
  reset: () => void;

  setStep: (step: AddSourceStep) => void;
  goBack: () => void;

  selectSource: (shortName: string, displayName: string) => void;
  clearSource: () => void;

  setConnectionName: (name: string) => void;
  setAuthMode: (mode: AuthMode) => void;
  setAuthField: (name: string, value: string) => void;
  setAuthFields: (fields: Record<string, string>) => void;
  setConfigField: (name: string, value: string | string[]) => void;
  setConfigFields: (fields: Record<string, string | string[]>) => void;

  setUseCustomOAuth: (use: boolean) => void;
  setClientId: (id: string) => void;
  setClientSecret: (secret: string) => void;
  setCustomRedirectUrl: (url: string) => void;

  setSelectedAuthProviderId: (id: string | null) => void;
  setAuthProviderConfig: (config: Record<string, string>) => void;

  setOAuthUrl: (url: string | null) => void;
  setCreatedConnectionId: (id: string | null) => void;

  completeWithOAuth: (connectionId: string, oauthUrl: string) => void;
  completeWithoutOAuth: (connectionId: string) => void;
}

const initialState = {
  isOpen: false,
  currentStep: "source-select" as AddSourceStep,
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
  createdConnectionId: null,
};

export const useAddSourceStore = create<AddSourceState>()(
  persist(
    (set, get) => ({
      ...initialState,

      open: (
        collectionId: string,
        collectionName: string,
        preSelectedSource?: { shortName: string; name: string }
      ) => {
        if (preSelectedSource) {
          set({
            ...initialState,
            isOpen: true,
            currentStep: "source-config",
            collectionId,
            collectionName,
            selectedSourceShortName: preSelectedSource.shortName,
            selectedSourceName: preSelectedSource.name,
            connectionName: `${preSelectedSource.name} Connection`,
          });
        } else {
          set({
            ...initialState,
            isOpen: true,
            currentStep: "source-select",
            collectionId,
            collectionName,
          });
        }
      },

      close: () => {
        set({ isOpen: false });
      },

      reset: () => {
        set(initialState);
      },

      setStep: (step: AddSourceStep) => {
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
          case "success":
            // No going back from success
            break;
          default:
            break;
        }
      },

      selectSource: (shortName: string, displayName: string) => {
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
          authProviderConfig: {},
        });
      },

      clearSource: () => {
        set({
          selectedSourceShortName: null,
          selectedSourceName: null,
          connectionName: "",
          authMode: null,
          authFields: {},
          configFields: {},
        });
      },

      setConnectionName: (name: string) => {
        set({ connectionName: name });
      },

      setAuthMode: (mode: AuthMode) => {
        set({
          authMode: mode,
          authFields: {},
          useCustomOAuth: false,
          clientId: "",
          clientSecret: "",
          selectedAuthProviderId: null,
          authProviderConfig: {},
        });
      },

      setAuthField: (name: string, value: string) => {
        set((state) => ({
          authFields: { ...state.authFields, [name]: value },
        }));
      },

      setAuthFields: (fields: Record<string, string>) => {
        set({ authFields: fields });
      },

      setConfigField: (name: string, value: string | string[]) => {
        set((state) => ({
          configFields: { ...state.configFields, [name]: value },
        }));
      },

      setConfigFields: (fields: Record<string, string | string[]>) => {
        set({ configFields: fields });
      },

      setUseCustomOAuth: (use: boolean) => {
        set({ useCustomOAuth: use });
      },

      setClientId: (id: string) => {
        set({ clientId: id });
      },

      setClientSecret: (secret: string) => {
        set({ clientSecret: secret });
      },

      setCustomRedirectUrl: (url: string) => {
        set({ customRedirectUrl: url });
      },

      setSelectedAuthProviderId: (id: string | null) => {
        set({
          selectedAuthProviderId: id,
          authProviderConfig: {},
        });
      },

      setAuthProviderConfig: (config: Record<string, string>) => {
        set({ authProviderConfig: config });
      },

      setOAuthUrl: (url: string | null) => {
        set({ oauthUrl: url });
      },

      setCreatedConnectionId: (id: string | null) => {
        set({ createdConnectionId: id });
      },

      completeWithOAuth: (connectionId: string, oauthUrl: string) => {
        set({
          createdConnectionId: connectionId,
          oauthUrl,
          currentStep: "oauth-pending",
        });
      },

      completeWithoutOAuth: (connectionId: string) => {
        set({
          createdConnectionId: connectionId,
          currentStep: "success",
        });
      },
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
        oauthUrl: state.oauthUrl,
      }),
    }
  )
);
