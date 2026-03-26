import type { OrganizationWithRole } from '@/shared/api/generated';

interface ResolveCurrentOrganizationInput {
  organizations: Array<OrganizationWithRole>;
  preferredOrganizationId?: string | null;
  primaryOrganizationId?: string | null;
}

export function resolveCurrentOrganizationId({
  organizations,
  preferredOrganizationId,
  primaryOrganizationId,
}: ResolveCurrentOrganizationInput) {
  if (organizations.length === 0) {
    return null;
  }

  if (preferredOrganizationId) {
    const matchingOrganization = organizations.find(
      (organization) => organization.id === preferredOrganizationId,
    );

    if (matchingOrganization) {
      return matchingOrganization.id;
    }
  }

  if (primaryOrganizationId) {
    const primaryOrganization = organizations.find(
      (organization) => organization.id === primaryOrganizationId,
    );

    if (primaryOrganization) {
      return primaryOrganization.id;
    }
  }

  const markedPrimaryOrganization = organizations.find(
    (organization) => organization.is_primary,
  );

  if (markedPrimaryOrganization) {
    return markedPrimaryOrganization.id;
  }

  return organizations[0]?.id ?? null;
}

export function resolveCurrentOrganization(
  input: ResolveCurrentOrganizationInput,
) {
  const currentOrganizationId = resolveCurrentOrganizationId(input);

  if (!currentOrganizationId) {
    return null;
  }

  return (
    input.organizations.find(
      (organization) => organization.id === currentOrganizationId,
    ) ?? null
  );
}

export function resolveRequiredCurrentOrganization(
  input: ResolveCurrentOrganizationInput,
) {
  const currentOrganization = resolveCurrentOrganization(input);

  if (!currentOrganization) {
    throw new Error('App session requires a current organization');
  }

  return currentOrganization;
}
