const assignableOrganizationMemberRoles = ['member', 'admin'] as const;

type AssignableOrganizationMemberRole =
  (typeof assignableOrganizationMemberRoles)[number];

function isAssignableOrganizationMemberRole(
  role: string,
): role is AssignableOrganizationMemberRole {
  return assignableOrganizationMemberRoles.includes(
    role as AssignableOrganizationMemberRole,
  );
}

function getOrganizationRoleLabel(role: string) {
  return role.charAt(0).toUpperCase() + role.slice(1).toLowerCase();
}

export {
  assignableOrganizationMemberRoles,
  getOrganizationRoleLabel,
  isAssignableOrganizationMemberRole,
};
export type { AssignableOrganizationMemberRole };
