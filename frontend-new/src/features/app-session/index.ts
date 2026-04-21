export {
  currentOrganizationsQueryOptions,
  currentUserQueryOptions,
  ensureAppSession,
  ensureCurrentUser,
  syncAuthUser,
  syncCurrentUser,
} from './api';
export type { AppSessionData, EnsureAppSessionResult } from './api';
export { MissingOrganizationError } from './lib/errors';
export {
  resolveCurrentOrganization,
  resolveCurrentOrganizationId,
  resolveRequiredCurrentOrganization,
} from './lib/selectors';
export { buildUserSyncPayload } from './lib/user-sync';
export {
  appSessionStore,
  clearPreferredOrganizationId,
  getPreferredOrganizationId,
  setPreferredOrganizationId,
} from './lib/store';
export { usePreferredOrganizationId } from './hooks/use-preferred-organization-id';
