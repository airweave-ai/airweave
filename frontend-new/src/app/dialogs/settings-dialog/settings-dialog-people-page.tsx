import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { IconPlus } from '@tabler/icons-react';
import { SettingsDialogLayout } from './settings-dialog-layout';
import {
  InviteOrganizationMemberDialog,
  OrganizationMembersTable,
  canManageOrganizationMembers,
  useOrganizationMembersQueryOptions,
} from '@/features/organizations';
import { ErrorState } from '@/shared/components/error-state';
import { LoadingState } from '@/shared/components/loading-state';
import { useAppSession } from '@/shared/session';
import { Button } from '@/shared/ui/button';
import { pluralize } from '@/shared/format/pluralize';

type SettingsDialogPeoplePageProps = {
  onClose: () => void;
};

function SettingsDialogPeoplePage({ onClose }: SettingsDialogPeoplePageProps) {
  const { currentOrganization, viewer } = useAppSession();
  const [inviteDialogOpen, setInviteDialogOpen] = React.useState(false);
  const organizationMembersQueryOptions = useOrganizationMembersQueryOptions();
  const {
    data: members,
    error,
    refetch,
  } = useQuery(organizationMembersQueryOptions);
  const canManageMembers = canManageOrganizationMembers(
    currentOrganization.role,
  );

  const body = error ? (
    <ErrorState
      title="We couldn't load members"
      description="There was a problem loading members for this organization."
      onRetry={() => {
        void refetch();
      }}
      retryLabel="Reload members"
    />
  ) : !members ? (
    <LoadingState title="Loading members..." />
  ) : (
    <OrganizationMembersTable
      canManageMembers={canManageMembers}
      currentUserId={viewer.id}
      members={members}
    />
  );

  const memberCount = members?.length ?? 0;
  return (
    <SettingsDialogLayout
      title="People"
      description="Manage people in your organization and their roles"
      className="overflow-hidden"
      onClose={onClose}
    >
      <div className="flex h-full min-h-0 flex-col gap-4">
        <div className="flex shrink-0 items-center justify-between gap-4">
          <div className="text-sm font-medium">
            <span>
              {memberCount} {pluralize(memberCount, 'Member')}
            </span>
          </div>
          {canManageMembers ? (
            <Button
              size="lg"
              onClick={() => setInviteDialogOpen(true)}
              type="button"
            >
              <IconPlus />
              Add New
            </Button>
          ) : null}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">{body}</div>
      </div>

      {members ? (
        <InviteOrganizationMemberDialog
          existingMemberEmails={members.map((member) => member.email)}
          open={inviteDialogOpen}
          organizationId={currentOrganization.id}
          onOpenChange={setInviteDialogOpen}
        />
      ) : null}
    </SettingsDialogLayout>
  );
}

export { SettingsDialogPeoplePage };
