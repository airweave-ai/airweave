/**
 * API client - Re-exports all API operations
 */

export { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

export { createApiKey, deleteApiKey, fetchApiKeys } from "./api-keys";
export type { APIKey } from "./api-keys";

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

export {
  cancelOrganizationInvitation,
  deleteOrganization,
  fetchOrganization,
  fetchOrganizationInvitations,
  fetchOrganizationMembers,
  fetchOrganizations,
  inviteOrganizationMemberWithResponse,
  removeOrganizationMember,
  setPrimaryOrganization,
  updateOrganization,
} from "./organizations";
export type {
  InviteResponse,
  Organization,
  OrganizationMember,
  PendingInvitation,
  UpdateOrganizationRequest,
} from "./organizations";

export {
  createCollection,
  deleteCollection,
  fetchCollection,
  fetchCollectionCount,
  fetchCollections,
} from "./collections";
export type { Collection, CreateCollectionRequest } from "./collections";

export { fetchSource, fetchSources } from "./sources";
export type {
  Source,
  AuthField as SourceAuthField,
  ConfigField as SourceConfigField,
} from "./sources";

export {
  cancelSourceConnectionSync,
  createSourceConnection,
  deleteSourceConnection,
  fetchSourceConnection,
  fetchSourceConnections,
  refreshAllSourceConnections,
  runSourceConnectionSync,
  updateSourceConnection,
} from "./source-connections";
export type {
  AuthenticationInfo,
  CreateSourceConnectionAuth,
  CreateSourceConnectionRequest,
  EntitySummary,
  EntityTypeStats,
  LastSyncJob,
  Schedule,
  SourceConnection,
  SyncJob,
  UpdateSourceConnectionRequest,
} from "./source-connections";
