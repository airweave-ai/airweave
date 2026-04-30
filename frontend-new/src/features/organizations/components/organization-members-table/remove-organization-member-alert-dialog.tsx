import { toast } from 'sonner';
import { IconUserX } from '@tabler/icons-react';
import { useRemoveOrganizationMemberMutation } from '../../api';
import type { MemberResponse } from '@/shared/api/generated';
import { useCurrentOrganizationId } from '@/shared/session';
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
} from '@/shared/ui/alert-dialog';
import { Button } from '@/shared/ui/button';

type RemoveOrganizationMemberAlertDialogProps = {
  member: MemberResponse | null;
  onOpenChange: (open: boolean) => void;
};

function RemoveOrganizationMemberAlertDialog({
  member,
  onOpenChange,
}: RemoveOrganizationMemberAlertDialogProps) {
  const organizationId = useCurrentOrganizationId();
  const removeMemberMutation = useRemoveOrganizationMemberMutation();

  const handleRemove = () => {
    if (!member) {
      return;
    }

    removeMemberMutation.mutate(
      {
        path: {
          organization_id: organizationId,
          user_id: member.id,
        },
      },
      {
        onSuccess: () => {
          toast.success(`${member.name} was removed.`);
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <AlertDialog
      open={!!member}
      onOpenChange={(open) => {
        if (!open && removeMemberMutation.isPending) {
          return;
        }

        onOpenChange(open);
      }}
    >
      <AlertDialogContent size="sm">
        <AlertDialogHeader>
          <AlertDialogMedia className="bg-destructive/10 text-destructive">
            <IconUserX className="size-5" />
          </AlertDialogMedia>
          <AlertDialogTitle>Delete Member?</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently remove this member from your organization. You
            cannot undo this action.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={removeMemberMutation.isPending}>
            Cancel
          </AlertDialogCancel>
          <Button
            disabled={removeMemberMutation.isPending}
            onClick={handleRemove}
            type="button"
            variant="destructive"
          >
            Delete
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export { RemoveOrganizationMemberAlertDialog };
