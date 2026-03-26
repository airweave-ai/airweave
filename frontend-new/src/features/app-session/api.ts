import type { UserCreate } from '@/shared/api/generated';
import {
  listUserOrganizationsOrganizationsGetOptions,
  readUserUsersGetOptions,
} from '@/shared/api/generated/@tanstack/react-query.gen';
import { createOrUpdateUserUsersCreateOrUpdatePost } from '@/shared/api/generated';

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
