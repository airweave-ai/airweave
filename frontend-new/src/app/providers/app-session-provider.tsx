import * as React from 'react';
import { useSuspenseQueries } from '@tanstack/react-query';
import {
  currentOrganizationsQueryOptions,
  currentUserQueryOptions,
  resolveRequiredCurrentOrganization,
  setPreferredOrganizationId,
  usePreferredOrganizationId,
} from '@/features/app-session';
import { useAuth } from '@/shared/auth';
import {
  AppSessionContext,
  type AppSessionValue,
  type AppSessionViewer,
} from '@/shared/session';

export function AppSessionProvider({ children }: React.PropsWithChildren) {
  const auth = useAuth();

  if (auth.status !== 'authenticated') {
    throw new Error('AppSessionProvider requires authenticated auth state');
  }

  const authUser = auth.user;
  const preferredOrganizationId = usePreferredOrganizationId();
  const [{ data: backendUser }, { data: organizations }] = useSuspenseQueries({
    queries: [currentUserQueryOptions(), currentOrganizationsQueryOptions()],
  });

  const currentOrganization = React.useMemo(
    () =>
      resolveRequiredCurrentOrganization({
        organizations,
        preferredOrganizationId,
        primaryOrganizationId: backendUser.primary_organization_id,
      }),
    [
      backendUser.primary_organization_id,
      organizations,
      preferredOrganizationId,
    ],
  );

  const currentOrganizationId = currentOrganization.id;

  const viewer = React.useMemo<AppSessionViewer>(
    () => ({
      auth0Id:
        backendUser.auth0_id ??
        (typeof authUser.sub === 'string' ? authUser.sub : null),
      email: backendUser.email,
      id: backendUser.id,
      isAdmin: backendUser.is_admin ?? false,
      isSuperuser: backendUser.is_superuser ?? false,
      name: backendUser.full_name ?? authUser.name ?? null,
      picture: authUser.picture ?? null,
      primaryOrganizationId: backendUser.primary_organization_id ?? null,
    }),
    [
      authUser.name,
      authUser.picture,
      authUser.sub,
      backendUser.auth0_id,
      backendUser.email,
      backendUser.full_name,
      backendUser.id,
      backendUser.is_admin,
      backendUser.is_superuser,
      backendUser.primary_organization_id,
    ],
  );

  const setCurrentOrganizationId = React.useCallback(
    (organizationId: string) => {
      if (
        !organizations.some(
          (organization) => organization.id === organizationId,
        )
      ) {
        return;
      }

      setPreferredOrganizationId(organizationId);
    },
    [organizations],
  );

  const value = React.useMemo<AppSessionValue>(
    () => ({
      backendUser,
      currentOrganization,
      currentOrganizationId,
      organizations,
      setCurrentOrganizationId,
      viewer,
    }),
    [
      backendUser,
      currentOrganization,
      currentOrganizationId,
      organizations,
      setCurrentOrganizationId,
      viewer,
    ],
  );

  return (
    <AppSessionContext.Provider value={value}>
      {children}
    </AppSessionContext.Provider>
  );
}
