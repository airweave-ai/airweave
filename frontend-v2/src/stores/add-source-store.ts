/**
 * Store for managing the "Add Source to Collection" flow
 *
 * This store handles the multi-step process of adding a source connection
 * to an existing collection:
 * 1. source-select: User browses and selects a source
 * 2. source-config: User configures auth and settings
 * 3. oauth-pending: User completes OAuth (if needed)
 * 4. success: Connection created successfully
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Steps in the add source flow
 */
export type AddSourceStep =
  | "source-select"
  | "source-config"
  | "oauth-pending"
  | "success";

/**
 * Authentication modes supported
 */
export type AuthMode = "oauth2" | "direct_auth" | "external_provider";

/**
 * State for the add source dialog
 */
interface AddSourceState {
  // Dialog state
  isOpen: boolean;
  currentStep: AddSourceStep;

  // Collection context (the collection we're adding to)
  collectionId: string | null;
  collectionName: string | null;

  // Source selection
  selectedSourceShortName: string | null;
  selectedSourceName: string | null;

  // Source configuration
  connectionName: string;
  authMode: AuthMode | null;
  authFields: Record<string, string>;
  configFields: Record<string, string | string[]>;

  // Custom OAuth credentials (BYOC)
  useCustomOAuth: boolean;
  clientId: string;
  clientSecret: string;
  customRedirectUrl: string;

  // External auth provider
  selectedAuthProviderId: string | null;
  authProviderConfig: Record<string, string>;

  // OAuth flow state
  oauthUrl: string | null;
  createdConnectionId: string | null;

  // Actions
  open: (collectionId: string, collectionName: string) => void;
  close: () => void;
  reset: () => void;

  // Step navigation
  setStep: (step: AddSourceStep) => void;
  goBack: () => void;

  // Source selection
  selectSource: (shortName: string, displayName: string) => void;
  clearSource: () => void;

  // Configuration
  setConnectionName: (name: string) => void;
  setAuthMode: (mode: AuthMode) => void;
  setAuthField: (name: string, value: string) => void;
  setAuthFields: (fields: Record<string, string>) => void;
  setConfigField: (name: string, value: string | string[]) => void;
  setConfigFields: (fields: Record<string, string | string[]>) => void;

  // Custom OAuth
  setUseCustomOAuth: (use: boolean) => void;
  setClientId: (id: string) => void;
  setClientSecret: (secret: string) => void;
  setCustomRedirectUrl: (url: string) => void;

  // External provider
  setSelectedAuthProviderId: (id: string | null) => void;
  setAuthProviderConfig: (config: Record<string, string>) => void;

  // OAuth flow
  setOAuthUrl: (url: string | null) => void;
  setCreatedConnectionId: (id: string | null) => void;

  // Success handling
  completeWithOAuth: (connectionId: string, oauthUrl: string) => void;
  completeWithoutOAuth: (connectionId: string) => void;
}

/**
 * Initial state values
 */
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

/**
 * Add Source Store
 */
export const useAddSourceStore = create<AddSourceState>()(
  persist(
    (set, get) => ({
      ...initialState,

      // Open the dialog for a specific collection
      open: (collectionId: string, collectionName: string) => {
        // Reset state first, then open
        set({
          ...initialState,
          isOpen: true,
          currentStep: "source-select",
          collectionId,
          collectionName,
        });
      },

      // Close the dialog
      close: () => {
        set({ isOpen: false });
      },

      // Reset all state
      reset: () => {
        set(initialState);
      },

      // Step navigation
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
            // Can't go back from success
            break;
          default:
            break;
        }
      },

      // Source selection
      selectSource: (shortName: string, displayName: string) => {
        set({
          selectedSourceShortName: shortName,
          selectedSourceName: displayName,
          connectionName: `${displayName} Connection`,
          currentStep: "source-config",
          // Reset config when changing source
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

      // Configuration setters
      setConnectionName: (name: string) => {
        set({ connectionName: name });
      },

      setAuthMode: (mode: AuthMode) => {
        set({
          authMode: mode,
          // Reset relevant fields when changing auth mode
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

      // Custom OAuth setters
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

      // External provider setters
      setSelectedAuthProviderId: (id: string | null) => {
        set({
          selectedAuthProviderId: id,
          authProviderConfig: {},
        });
      },

      setAuthProviderConfig: (config: Record<string, string>) => {
        set({ authProviderConfig: config });
      },

      // OAuth flow
      setOAuthUrl: (url: string | null) => {
        set({ oauthUrl: url });
      },

      setCreatedConnectionId: (id: string | null) => {
        set({ createdConnectionId: id });
      },

      // Success handling
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
        // Don't persist isOpen to avoid stale modal state
      }),
    }
  )
);
