import * as React from 'react';
import type { OrganizationWithRole, User } from '@/shared/api/generated';

export interface AppSessionViewer {
  auth0Id: string | null;
  email: string;
  id: string;
  isAdmin: boolean;
  isSuperuser: boolean;
  name: string | null;
  picture: string | null;
  primaryOrganizationId: string | null;
}

export interface AppSessionValue {
  backendUser: User;
  currentOrganization: OrganizationWithRole;
  currentOrganizationId: string;
  organizations: Array<OrganizationWithRole>;
  setCurrentOrganizationId: (organizationId: string) => void;
  viewer: AppSessionViewer;
}

export const AppSessionContext = React.createContext<
  AppSessionValue | undefined
>(undefined);

export function useAppSession() {
  const context = React.useContext(AppSessionContext);

  if (!context) {
    throw new Error('useAppSession must be used within AppSessionProvider');
  }

  return context;
}

export function useCurrentOrganizationId() {
  return useAppSession().currentOrganizationId;
}

export function useCurrentOrganization() {
  return useAppSession().currentOrganization;
}
