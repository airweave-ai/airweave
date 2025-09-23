import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type CreationStep =
  | 'collection-form'
  | 'source-select'
  | 'source-config'
  | 'oauth-redirect'
  | 'success';

export type AuthMode = 'oauth2' | 'direct_auth' | 'external_provider' | 'config_auth';

// Flow types to track entry point
export type FlowType =
  | 'create-collection'        // From DashboardLayout - no preselection
  | 'create-with-source'       // From Dashboard - source preselected
  | 'add-to-collection';       // From CollectionDetailView - collection exists

interface CollectionCreationState {
  // Modal state
  isOpen: boolean;
  currentStep: CreationStep;
  flowType: FlowType;

  // Collection data
  collectionName: string;
  collectionDescription: string;
  collectionId?: string; // Set after creation or passed in for add-to-collection
  existingCollectionId?: string; // For add-to-collection flow
  existingCollectionName?: string; // For add-to-collection flow

  // Source connection data
  selectedSource?: string; // short_name
  sourceName?: string; // Display name
  sourceConnectionName?: string; // User-provided connection name
  authMode?: AuthMode;
  authConfig?: Record<string, any>;
  configFields?: Record<string, any>;

  // Auth provider data
  selectedAuthProvider?: string; // readable_id of auth provider connection
  authProviderConfig?: Record<string, any>; // Provider-specific config (e.g. auth_config_id, account_id)

  // OAuth flow state
  oauthState?: string;
  redirectUrl?: string;
  authenticationUrl?: string;
  connectionId?: string; // Set after successful connection

  // Actions
  openModal: (startStep?: CreationStep) => void;
  openForCreateCollection: () => void;
  openForCreateWithSource: (sourceShortName: string, sourceName: string, authMode?: AuthMode) => void;
  openForAddToCollection: (collectionId: string, collectionName: string) => void;
  closeModal: () => void;
  setStep: (step: CreationStep) => void;
  handleBackFromSourceConfig: () => Promise<void>;

  // Collection actions
  setCollectionData: (name: string, description?: string) => void;
  setCollectionId: (id: string) => void;

  // Source actions
  selectSource: (shortName: string, displayName: string) => void;
  setSourceConnectionName: (name: string) => void;
  setAuthMode: (mode: AuthMode) => void;
  setAuthConfig: (config: Record<string, any>) => void;
  setConfigFields: (fields: Record<string, any>) => void;

  // Auth provider actions
  setSelectedAuthProvider: (providerId: string | undefined) => void;
  setAuthProviderConfig: (config: Record<string, any>) => void;

  // OAuth actions
  setOAuthData: (state: string, redirectUrl: string, authUrl?: string) => void;
  setConnectionId: (id: string) => void;

  // Reset
  reset: () => void;
  resetSourceData: () => void;

  // Helper getters
  isAddingToExistingCollection: () => boolean;
  getInitialStep: () => CreationStep;
}

const initialState = {
  isOpen: false,
  currentStep: 'collection-form' as CreationStep,
  flowType: 'create-collection' as FlowType,
  collectionName: '',
  collectionDescription: '',
  collectionId: undefined,
  existingCollectionId: undefined,
  existingCollectionName: undefined,
  selectedSource: undefined,
  sourceName: undefined,
  sourceConnectionName: undefined,
  authMode: undefined,
  authConfig: undefined,
  configFields: undefined,
  selectedAuthProvider: undefined,
  authProviderConfig: undefined,
  oauthState: undefined,
  redirectUrl: undefined,
  authenticationUrl: undefined,
  connectionId: undefined,
};

export const useCollectionCreationStore = create<CollectionCreationState>()(
  persist(
    (set, get) => ({
      ...initialState,

      openModal: (startStep = 'collection-form') => set({ isOpen: true, currentStep: startStep }),

      // Flow-specific open methods
      openForCreateCollection: () => {
        // Clear any previous state first
        const currentState = get();
        if (currentState.isOpen) {
          set({ isOpen: false });
        }

        // Then open with new state
        setTimeout(() => {
          set({
            ...initialState,
            isOpen: true,
            flowType: 'create-collection',
            currentStep: 'collection-form', // Start with collection form to get the name first
          });
        }, 50);
      },

      openForCreateWithSource: (sourceShortName, sourceName, authMode) => {
        // Clear any previous state first
        const currentState = get();
        if (currentState.isOpen) {
          set({ isOpen: false });
        }

        // Then open with new state
        setTimeout(() => {
          set({
            ...initialState,
            isOpen: true,
            flowType: 'create-with-source',
            currentStep: 'collection-form', // Start with collection form since source is preselected
            selectedSource: sourceShortName,
            sourceName: sourceName,
            authMode: authMode,
          });
        }, 50);
      },

      openForAddToCollection: (collectionId, collectionName) => {
        // Clear any previous state first
        const currentState = get();
        if (currentState.isOpen) {
          set({ isOpen: false });
        }

        // Then open with new state
        setTimeout(() => {
          set({
            ...initialState,
            isOpen: true,
            flowType: 'add-to-collection',
            currentStep: 'source-select', // Start with source selection
            existingCollectionId: collectionId,
            existingCollectionName: collectionName,
            collectionId: collectionId, // Set this for the flow
            collectionName: collectionName, // Use existing name
          });
        }, 50);
      },

      closeModal: () => {
        set({ isOpen: false });
        // Don't automatically reset state here - let components handle it
      },

      setStep: (step) => set({ currentStep: step }),

      handleBackFromSourceConfig: async () => {
        const state = get();

        // If we created a collection and are going back, delete it
        // (but not for add-to-collection flow where we're using an existing collection)
        if (state.collectionId && state.flowType !== 'add-to-collection') {
          try {
            // Import apiClient dynamically to avoid circular dependency
            const { apiClient } = await import('@/lib/api');
            const response = await apiClient.delete(`/collections/${state.collectionId}`);
            if (response.ok) {
              console.log('Deleted temporary collection:', state.collectionId);
            }
          } catch (error) {
            console.error('Failed to delete collection on back navigation:', error);
          }

          // Clear the collection ID since we deleted it
          set({ collectionId: undefined });
        }

        // If we're in create-with-source flow, keep the source and go back to collection form
        if (state.flowType === 'create-with-source') {
          // Don't clear the source - it was pre-selected from Dashboard
          set({ currentStep: 'collection-form' });
        } else if (state.flowType === 'add-to-collection') {
          // For add-to-collection, go back to source select
          set({ currentStep: 'source-select' });
        } else {
          // For create-collection flow, go back to source select
          set({ currentStep: 'source-select' });
        }
      },

      setCollectionData: (name, description) => set({
        collectionName: name,
        collectionDescription: description || ''
      }),

      setCollectionId: (id) => set({ collectionId: id }),

      selectSource: (shortName, displayName) => set({
        selectedSource: shortName,
        sourceName: displayName,
        sourceConnectionName: undefined // Clear previous connection name when switching sources
      }),

      setSourceConnectionName: (name) => set({ sourceConnectionName: name }),

      setAuthMode: (mode) => set({ authMode: mode }),
      setAuthConfig: (config) => set({ authConfig: config }),
      setConfigFields: (fields) => set({ configFields: fields }),

      setSelectedAuthProvider: (providerId) => set({ selectedAuthProvider: providerId }),
      setAuthProviderConfig: (config) => set({ authProviderConfig: config }),

      setOAuthData: (state, redirectUrl, authUrl) => set({
        oauthState: state,
        redirectUrl: redirectUrl,
        authenticationUrl: authUrl
      }),

      setConnectionId: (id) => set({ connectionId: id }),

      reset: () => set(initialState),

      resetSourceData: () => set({
        selectedSource: undefined,
        sourceName: undefined,
        sourceConnectionName: undefined,
        authMode: undefined,
        authConfig: undefined,
        configFields: undefined,
        selectedAuthProvider: undefined,
        authProviderConfig: undefined,
        oauthState: undefined,
        redirectUrl: undefined,
        authenticationUrl: undefined,
        connectionId: undefined,
      }),

      // Helper getters
      isAddingToExistingCollection: () => {
        const state = get();
        return state.flowType === 'add-to-collection';
      },

      getInitialStep: () => {
        const state = get();
        switch (state.flowType) {
          case 'create-collection':
            return 'collection-form'; // Start with collection form to get the name
          case 'create-with-source':
            return 'collection-form';
          case 'add-to-collection':
            return 'source-select';
          default:
            return 'collection-form';
        }
      },
    }),
    {
      name: 'collection-creation-storage',
      partialize: (state) => ({
        // Only persist what's needed for OAuth redirect
        // DO NOT persist isOpen to avoid modal getting stuck
        flowType: state.flowType,
        collectionId: state.collectionId,
        collectionName: state.collectionName,
        existingCollectionId: state.existingCollectionId,
        existingCollectionName: state.existingCollectionName,
        selectedSource: state.selectedSource,
        sourceName: state.sourceName,
        sourceConnectionName: state.sourceConnectionName,
        authMode: state.authMode,
        configFields: state.configFields,
        oauthState: state.oauthState,
        redirectUrl: state.redirectUrl,
      }),
    }
  )
);
