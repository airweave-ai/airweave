import {
  currentOrganizationsQueryOptions,
  currentUserQueryOptions,
} from './api';
import { syncAuthUser } from './user-sync';
import type { QueryClient } from '@tanstack/react-query';
import type { User } from '@/shared/api/generated';
import type { AuthUser } from '@/shared/auth';
import { hasApiErrorDetail } from '@/shared/api';

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
