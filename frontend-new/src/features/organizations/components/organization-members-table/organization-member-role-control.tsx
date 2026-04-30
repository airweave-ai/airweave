import { toast } from 'sonner';
import { useChangeOrganizationMemberRoleMutation } from '../../api';
import {
  assignableOrganizationMemberRoles,
  getOrganizationRoleLabel,
  isAssignableOrganizationMemberRole,
} from '../../lib/roles';
import { OrganizationRoleBadge } from '../organization-role-badge';
import type { AssignableOrganizationMemberRole } from '../../lib/roles';
import type { MemberResponse } from '@/shared/api/generated';
import { useCurrentOrganizationId } from '@/shared/session';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from '@/shared/ui/select';

type OrganizationMemberRoleControlProps = {
  canChangeRole: boolean;
  member: MemberResponse;
};

function OrganizationMemberRoleControl({
  canChangeRole,
  member,
}: OrganizationMemberRoleControlProps) {
  const organizationId = useCurrentOrganizationId();
  const changeRoleMutation = useChangeOrganizationMemberRoleMutation();
  const role = member.role;

  const handleRoleChange = (nextRole: AssignableOrganizationMemberRole) => {
    if (role === nextRole) {
      return;
    }

    changeRoleMutation.mutate(
      {
        body: { role: nextRole },
        path: {
          organization_id: organizationId,
          user_id: member.id,
        },
      },
      {
        onSuccess: () => {
          toast.success(
            `${member.name} is now ${getOrganizationRoleLabel(nextRole)}.`,
          );
        },
      },
    );
  };

  if (!canChangeRole || !isAssignableOrganizationMemberRole(role)) {
    return <OrganizationRoleBadge role={role} />;
  }

  return (
    <Select
      disabled={changeRoleMutation.isPending}
      value={role}
      onValueChange={(value: AssignableOrganizationMemberRole) =>
        handleRoleChange(value)
      }
    >
      <SelectTrigger
        aria-label={`Change role for ${member.name}`}
        className="w-fit justify-start border-transparent px-0 shadow-none hover:bg-muted/40 dark:bg-transparent"
      >
        <OrganizationRoleBadge role={role} />
      </SelectTrigger>
      <SelectContent align="start">
        {assignableOrganizationMemberRoles.map((option) => (
          <SelectItem key={option} value={option}>
            {getOrganizationRoleLabel(option)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export { OrganizationMemberRoleControl };
