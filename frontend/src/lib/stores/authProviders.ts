import { create } from 'zustand';
import { apiClient } from '@/lib/api';

// Field definition interface matching backend Fields schema
export interface AuthField {
    name: string;
    title?: string;
    description?: string;
    type?: string;
    required?: boolean;
    secret?: boolean;
}

export interface AuthFields {
    fields: AuthField[];
}

export interface AuthProvider {
    name: string;
    short_name: string;
    description?: string;
    class_name: string;
    auth_config_class: string;
    config_class: string;
    auth_fields?: AuthFields;
    config_fields?: AuthFields;
}

export interface AuthProviderConnection {
    id: string;
    name: string;
    readable_id: string;
    short_name: string;
    description?: string;
    created_by_email?: string;
    modified_by_email?: string;
    created_at: string;
    modified_at: string;
    masked_client_id?: string;  // Masked client ID for OAuth providers (e.g., "cli_abc...xyz")
}

interface AuthProvidersStore {
    authProviders: AuthProvider[];
    authProviderConnections: AuthProviderConnection[];
    isLoading: boolean;
    isLoadingConnections: boolean;
    error: string | null;
    fetchAuthProviders: () => Promise<AuthProvider[]>;
    fetchAuthProviderConnections: () => Promise<AuthProviderConnection[]>;
    isAuthProviderConnected: (shortName: string) => boolean;
    getConnectionForProvider: (shortName: string) => AuthProviderConnection | undefined;
    clearAuthProviderConnections: () => void;
}

export const useAuthProvidersStore = create<AuthProvidersStore>((set, get) => ({
    authProviders: [],
    authProviderConnections: [],
    isLoading: false,
    isLoadingConnections: false,
    error: null,

    fetchAuthProviders: async () => {
        // Return cached data if available and not loading
        const currentState = get();
        if (currentState.authProviders.length > 0 && !currentState.isLoading) {
            return currentState.authProviders;
        }

        set({ isLoading: true, error: null });

        try {
            const response = await apiClient.get('/auth-providers/list');

            if (!response.ok) {
                throw new Error(`Failed to fetch auth providers: ${response.status}`);
            }

            const authProviders = await response.json();
            set({ authProviders, isLoading: false });
            return authProviders;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Failed to fetch auth providers';
            set({ error: errorMessage, isLoading: false });
            throw error;
        }
    },

    fetchAuthProviderConnections: async () => {
        set({ isLoadingConnections: true, error: null });

        try {
            const response = await apiClient.get('/auth-providers/connections/');

            if (!response.ok) {
                throw new Error(`Failed to fetch auth provider connections: ${response.status}`);
            }

            const authProviderConnections = await response.json();
            set({ authProviderConnections, isLoadingConnections: false });
            return authProviderConnections;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Failed to fetch auth provider connections';
            set({ error: errorMessage, isLoadingConnections: false });
            throw error;
        }
    },

    isAuthProviderConnected: (shortName: string) => {
        const { authProviderConnections } = get();
        return authProviderConnections.some(connection => connection.short_name === shortName);
    },

    getConnectionForProvider: (shortName: string) => {
        const { authProviderConnections } = get();
        return authProviderConnections.find(connection => connection.short_name === shortName);
    },

    clearAuthProviderConnections: () => {
        console.log("🧹 [AuthProvidersStore] Clearing auth provider connections");
        set({ authProviderConnections: [] });
    }
}));
