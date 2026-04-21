import type { UserCreate } from '@/shared/api/generated';
import type { AuthUser } from '@/shared/auth';

export function buildUserSyncPayload(authUser: AuthUser): UserCreate | null {
  if (!authUser.email) {
    return null;
  }

  return {
    auth0_id: typeof authUser.sub === 'string' ? authUser.sub : null,
    email: authUser.email,
    full_name: typeof authUser.name === 'string' ? authUser.name : null,
  };
}
