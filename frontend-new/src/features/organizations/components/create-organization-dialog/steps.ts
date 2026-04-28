const steps = ['organization-name', 'organization-size'] as const;

type CreateOrganizationStep = (typeof steps)[number];

export { steps };
export type { CreateOrganizationStep };
