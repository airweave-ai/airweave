/**
 * API client - Re-exports all API operations
 */

// Client utilities
export { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

// API Keys
export type { APIKey } from "./api-keys";
export { createApiKey, deleteApiKey, fetchApiKeys } from "./api-keys";

// Auth Providers
export type {
  AuthField,
  AuthFields,
  AuthProvider,
  AuthProviderConnection,
  CreateAuthProviderConnectionRequest,
  UpdateAuthProviderConnectionRequest,
} from "./auth-providers";
export {
  createAuthProviderConnection,
  deleteAuthProviderConnection,
  fetchAuthProviderConnection,
  fetchAuthProviderConnections,
  fetchAuthProviderDetail,
  fetchAuthProviders,
  updateAuthProviderConnection,
} from "./auth-providers";
