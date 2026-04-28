import { mutationOptions, useMutation } from '@tanstack/react-query';
import { createOrganizationOrganizationsPostMutation } from '@/shared/api';

const organizationInvalidationTags = ['organizations'] as const;

export function createOrganizationMutationOptions() {
  return mutationOptions({
    ...createOrganizationOrganizationsPostMutation(),
    meta: {
      invalidateTags: organizationInvalidationTags,
    },
  });
}

export function useCreateOrganizationMutation() {
  return useMutation(createOrganizationMutationOptions());
}
