import * as React from 'react';
import { mutationOptions, useMutation } from '@tanstack/react-query';
import {
  changeMemberRoleOrganizationsOrganizationIdMembersUserIdPatchMutation,
  createOrganizationOrganizationsPostMutation,
  getOrganizationMembersOrganizationsOrganizationIdMembersGetOptions,
  inviteUserToOrganizationOrganizationsOrganizationIdInvitePostMutation,
  removeMemberFromOrganizationOrganizationsOrganizationIdMembersUserIdDeleteMutation,
  withOrganizationHeaders,
} from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

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

export function organizationMembersQueryOptions(organizationId: string) {
  const params: Parameters<
    typeof getOrganizationMembersOrganizationsOrganizationIdMembersGetOptions
  >[0] = {
    path: {
      organization_id: organizationId,
    },
  };
  return getOrganizationMembersOrganizationsOrganizationIdMembersGetOptions(
    withOrganizationHeaders({ organizationId }, params),
  );
}

export function useOrganizationMembersQueryOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => organizationMembersQueryOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function inviteOrganizationMemberMutationOptions(
  organizationId: string,
) {
  return mutationOptions({
    ...inviteUserToOrganizationOrganizationsOrganizationIdInvitePostMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      errorToast: 'Could not invite organization member.',
      invalidateTags: organizationInvalidationTags,
    },
  });
}

export function useInviteOrganizationMemberMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => inviteOrganizationMemberMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useInviteOrganizationMemberMutation() {
  const options = useInviteOrganizationMemberMutationOptions();
  return useMutation(options);
}

export function changeOrganizationMemberRoleMutationOptions(
  organizationId: string,
) {
  return mutationOptions({
    ...changeMemberRoleOrganizationsOrganizationIdMembersUserIdPatchMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      errorToast: 'Could not change organization member role.',
      invalidateTags: organizationInvalidationTags,
    },
  });
}

export function useChangeOrganizationMemberRoleMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => changeOrganizationMemberRoleMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useChangeOrganizationMemberRoleMutation() {
  const options = useChangeOrganizationMemberRoleMutationOptions();
  return useMutation(options);
}

export function removeOrganizationMemberMutationOptions(
  organizationId: string,
) {
  return mutationOptions({
    ...removeMemberFromOrganizationOrganizationsOrganizationIdMembersUserIdDeleteMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      errorToast: 'Could not remove organization member.',
      invalidateTags: organizationInvalidationTags,
    },
  });
}

export function useRemoveOrganizationMemberMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => removeOrganizationMemberMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useRemoveOrganizationMemberMutation() {
  const options = useRemoveOrganizationMemberMutationOptions();
  return useMutation(options);
}
