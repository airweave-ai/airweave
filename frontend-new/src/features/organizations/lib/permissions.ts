const rolesAllowedToManageOrganizationMembers = ['owner', 'admin'] as const;

type RoleAllowerToManageOrganizationMembers =
  (typeof rolesAllowedToManageOrganizationMembers)[number];

function canManageOrganizationMembers(
  role: string,
): role is RoleAllowerToManageOrganizationMembers {
  return rolesAllowedToManageOrganizationMembers.includes(
    role as RoleAllowerToManageOrganizationMembers,
  );
}

export { canManageOrganizationMembers };
