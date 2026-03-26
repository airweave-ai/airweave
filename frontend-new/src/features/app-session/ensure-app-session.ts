import { MissingOrganizationError } from './errors';
import {
  currentOrganizationsQueryOptions,
  currentUserQueryOptions,
} from './api';
import {
  resolveCurrentOrganizationId,
  resolveRequiredCurrentOrganization,
} from './selectors';
import { getPreferredOrganizationId } from './store';
import type { QueryClient } from '@tanstack/react-query';
import type { OrganizationWithRole, User } from '@/shared/api/generated';
import type { Result } from '@/shared/types/result';

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
