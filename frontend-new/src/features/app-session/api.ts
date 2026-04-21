import { MissingOrganizationError } from './lib/errors';
import {
  resolveCurrentOrganizationId,
  resolveRequiredCurrentOrganization,
} from './lib/selectors';
import { getPreferredOrganizationId } from './lib/store';
import { buildUserSyncPayload } from './lib/user-sync';
import type {
  OrganizationWithRole,
  User,
  UserCreate,
} from '@/shared/api/generated';
import type { QueryClient } from '@tanstack/react-query';
import type { AuthUser } from '@/shared/auth';
import type { Result } from '@/shared/types/result';
import { createOrUpdateUserUsersCreateOrUpdatePost } from '@/shared/api/generated';
import {
  listUserOrganizationsOrganizationsGetOptions,
  readUserUsersGetOptions,
} from '@/shared/api/generated/@tanstack/react-query.gen';
import { hasApiErrorDetail } from '@/shared/api';

export interface AppSessionData {
  currentOrganization: OrganizationWithRole;
  currentOrganizationId: string;
  organizations: Array<OrganizationWithRole>;
  user: User;
}

export type EnsureAppSessionResult = Result<
  AppSessionData,
  MissingOrganizationError
>;

export function currentOrganizationsQueryOptions() {
  return listUserOrganizationsOrganizationsGetOptions();
}

export function currentUserQueryOptions() {
  return readUserUsersGetOptions();
}

export async function syncCurrentUser(user: UserCreate) {
  const { data } = await createOrUpdateUserUsersCreateOrUpdatePost({
    body: user,
    throwOnError: true,
  });

  return data;
}

export function syncAuthUser(authUser: AuthUser) {
  const payload = buildUserSyncPayload(authUser);

  if (!payload) {
    throw new Error('Auth user is missing required fields for backend sync');
  }

  return syncCurrentUser(payload);
}

function isMissingCurrentUserError(error: unknown) {
  return hasApiErrorDetail(error, 'User not found');
}

export async function ensureCurrentUser({
  authUser,
  queryClient,
}: {
  authUser: AuthUser;
  queryClient: QueryClient;
}): Promise<User> {
  try {
    return await queryClient.ensureQueryData(currentUserQueryOptions());
  } catch (error) {
    if (!isMissingCurrentUserError(error)) {
      throw error;
    }

    await syncAuthUser(authUser);
    queryClient.removeQueries(currentUserQueryOptions());
    queryClient.removeQueries(currentOrganizationsQueryOptions());

    return queryClient.ensureQueryData(currentUserQueryOptions());
  }
}

export async function ensureAppSession({
  queryClient,
}: {
  queryClient: QueryClient;
}): Promise<EnsureAppSessionResult> {
  const user = await queryClient.ensureQueryData(currentUserQueryOptions());
  const organizations = await queryClient.ensureQueryData(
    currentOrganizationsQueryOptions(),
  );
  const preferredOrganizationId = getPreferredOrganizationId();
  const currentOrganizationId = resolveCurrentOrganizationId({
    organizations,
    preferredOrganizationId,
    primaryOrganizationId: user.primary_organization_id,
  });

  if (!currentOrganizationId) {
    return {
      data: null,
      error: new MissingOrganizationError(),
    };
  }

  const currentOrganization = resolveRequiredCurrentOrganization({
    organizations,
    preferredOrganizationId,
    primaryOrganizationId: user.primary_organization_id,
  });

  return {
    data: {
      currentOrganization,
      currentOrganizationId,
      organizations,
      user,
    },
    error: null,
  };
}
