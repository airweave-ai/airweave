import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import { toast } from 'sonner';
import * as z from 'zod';
import { useInviteOrganizationMemberMutation } from '../api';
import {
  assignableOrganizationMemberRoles,
  getOrganizationRoleLabel,
} from '../lib/roles';
import type { AssignableOrganizationMemberRole } from '../lib/roles';
import { Button } from '@/shared/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog';
import { Field, FieldError, FieldLabel } from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select';

const defaultFormValues = {
  email: '',
  role: 'member' as AssignableOrganizationMemberRole,
};

const roleOptions = [
  {
    role: 'member',
    description: 'They can access the organization and use its resources.',
  },
  {
    role: 'admin',
    description:
      'They have the ability to update the organization and manage its members and roles. However, please note that they cannot delete the organization.',
  },
] satisfies Array<{
  role: AssignableOrganizationMemberRole;
  description: string;
}>;

type InviteOrganizationMemberDialogProps = {
  existingMemberEmails: Array<string>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  organizationId: string;
};

function InviteOrganizationMemberDialog({
  existingMemberEmails,
  onOpenChange,
  open,
  organizationId,
}: InviteOrganizationMemberDialogProps) {
  const inviteMemberMutation = useInviteOrganizationMemberMutation();
  const existingMemberEmailSet = React.useMemo(
    () => new Set(existingMemberEmails.map((value) => value.toLowerCase())),
    [existingMemberEmails],
  );
  const formSchema = React.useMemo(
    () =>
      z.object({
        email: z
          .email('Enter a valid email address.')
          .trim()
          .refine(
            (value) => !existingMemberEmailSet.has(value.toLowerCase()),
            'This person is already a member.',
          ),
        role: z.enum(assignableOrganizationMemberRoles),
      }),
    [existingMemberEmailSet],
  );

  const form = useForm({
    defaultValues: defaultFormValues,
    validators: {
      onSubmit: formSchema,
    },
    onSubmit: async ({ value }) => {
      const values = formSchema.parse(value);

      await inviteMemberMutation.mutateAsync({
        body: values,
        path: {
          organization_id: organizationId,
        },
      });

      toast.success(`Invitation sent to ${values.email}.`);
      form.reset();
      onOpenChange(false);
    },
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && inviteMemberMutation.isPending) {
          return;
        }

        if (!nextOpen) {
          form.reset();
        }

        onOpenChange(nextOpen);
      }}
    >
      <DialogContent className="bg-background sm:max-w-3xl">
        <form
          noValidate
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            void form.handleSubmit();
          }}
        >
          <DialogHeader>
            <DialogTitle>Add Member</DialogTitle>
            <DialogDescription className="font-mono">
              Type or paste one email below.
            </DialogDescription>
          </DialogHeader>

          <form.Field name="email">
            {(field) => (
              <Field data-invalid={!field.state.meta.isValid}>
                <FieldLabel htmlFor={field.name}>Email</FieldLabel>
                <Input
                  id={field.name}
                  aria-invalid={!field.state.meta.isValid}
                  autoComplete="email"
                  disabled={inviteMemberMutation.isPending}
                  onBlur={field.handleBlur}
                  onChange={(event) => field.handleChange(event.target.value)}
                  placeholder="john@smith.com"
                  type="email"
                  value={field.state.value}
                />
                <FieldError errors={field.state.meta.errors} />
              </Field>
            )}
          </form.Field>

          <form.Field name="role">
            {(field) => (
              <Field data-invalid={!field.state.meta.isValid}>
                <FieldLabel htmlFor={field.name}>Select Role</FieldLabel>
                <Select
                  disabled={inviteMemberMutation.isPending}
                  onValueChange={(value) =>
                    field.handleChange(
                      value as AssignableOrganizationMemberRole,
                    )
                  }
                  value={field.state.value}
                >
                  <SelectTrigger
                    id={field.name}
                    className="h-auto min-h-21 w-full py-2.5"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {roleOptions.map(({ role, description }) => (
                      <SelectItem
                        key={role}
                        value={role}
                        className="items-start py-2.5"
                      >
                        <RoleOptionContent
                          role={role}
                          description={description}
                        />
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FieldError errors={field.state.meta.errors} />
              </Field>
            )}
          </form.Field>

          <DialogFooter>
            <DialogClose asChild>
              <Button
                className="sm:w-30"
                disabled={inviteMemberMutation.isPending}
                type="button"
                variant="outline"
              >
                Cancel
              </Button>
            </DialogClose>
            <Button
              className="sm:flex-1"
              disabled={inviteMemberMutation.isPending}
              type="submit"
            >
              Send Invite
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RoleOptionContent({
  role,
  description,
}: {
  role: AssignableOrganizationMemberRole;
  description: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 text-left whitespace-normal">
      <span className="font-medium text-foreground">
        {getOrganizationRoleLabel(role)}
      </span>
      <span className="line-clamp-2 text-muted-foreground">{description}</span>
    </div>
  );
}

export { InviteOrganizationMemberDialog };
