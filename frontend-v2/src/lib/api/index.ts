/**
 * API client - Re-exports all API operations
 */

// Client utilities
export { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

// API Keys
export { createApiKey, deleteApiKey, fetchApiKeys } from "./api-keys";
export type { APIKey } from "./api-keys";

// Auth Providers
export {
  createAuthProviderConnection,
  deleteAuthProviderConnection,
  fetchAuthProviderConnection,
  fetchAuthProviderConnections,
  fetchAuthProviderDetail,
  fetchAuthProviders,
  updateAuthProviderConnection,
} from "./auth-providers";
export type {
  AuthField,
  AuthFields,
  AuthProvider,
  AuthProviderConnection,
  CreateAuthProviderConnectionRequest,
  UpdateAuthProviderConnectionRequest,
} from "./auth-providers";

// Organizations
export { fetchOrganization, fetchOrganizations } from "./organizations";
export type { Organization } from "./organizations";

// Collections
export {
  createCollection,
  deleteCollection,
  fetchCollection,
  fetchCollectionCount,
  fetchCollections,
} from "./collections";
export type { Collection, CreateCollectionRequest } from "./collections";

// Sources
export { fetchSource, fetchSources } from "./sources";
export type {
  AuthField as SourceAuthField,
  ConfigField as SourceConfigField,
  Source,
} from "./sources";
