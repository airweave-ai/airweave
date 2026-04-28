import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import { IconArrowRight } from '@tabler/icons-react';
import * as z from 'zod';
import { CreateOrganizationDialogLayout } from './create-organization-dialog-layout';
import { Button } from '@/shared/ui/button';
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';

const organizationNameSchema = z
  .string()
  .trim()
  .min(4, 'Organization name must be at least 4 characters')
  .max(100, 'Organization name must be at most 100 characters')
  .regex(
    /^[A-Za-z0-9 _-]+$/,
    'Use letters, numbers, spaces, hyphens, and underscores only',
  );

const organizationNameFormSchema = z.object({
  organizationName: organizationNameSchema,
});

type OrganizationNameFormInput = z.input<typeof organizationNameFormSchema>;
type OrganizationNameFormOutput = z.output<typeof organizationNameFormSchema>;

interface OrganizationNameStepProps {
  defaultValue?: OrganizationNameFormInput;
  isPending: boolean;
  onCancel: () => void;
  onSubmit: (value: OrganizationNameFormOutput) => void;
}

function OrganizationNameStep({
  defaultValue,
  isPending,
  onCancel,
  onSubmit,
}: OrganizationNameStepProps) {
  const formId = React.useId();
  const form = useForm({
    defaultValues: defaultValue ?? {
      organizationName: '',
    },
    validators: {
      onSubmit: organizationNameFormSchema,
    },
    onSubmit: ({ value }) => {
      const values = organizationNameFormSchema.parse(value);

      onSubmit(values);
    },
  });

  const footer = (
    <>
      <Button
        className="w-full sm:w-30"
        disabled={isPending}
        onClick={onCancel}
        type="button"
        variant="outline"
      >
        Close
      </Button>
      <Button
        className="w-full sm:w-100"
        disabled={isPending}
        form={formId}
        type="submit"
      >
        Continue
        <IconArrowRight className="size-4" />
      </Button>
    </>
  );

  return (
    <CreateOrganizationDialogLayout
      description="Choose a name that represents your team or company"
      footer={footer}
      onClose={onCancel}
      step="organization-name"
      title="What should we call your organization?"
    >
      <form
        className="mx-auto grid w-full max-w-201 gap-4"
        id={formId}
        onSubmit={(event) => {
          event.preventDefault();
          void form.handleSubmit();
        }}
      >
        <form.Field name="organizationName">
          {(field) => (
            <Field data-invalid={!field.state.meta.isValid}>
              <FieldLabel htmlFor={field.name}>Organization name</FieldLabel>
              <Input
                aria-invalid={!field.state.meta.isValid}
                autoFocus
                disabled={isPending}
                id={field.name}
                onBlur={field.handleBlur}
                onChange={(event) => field.handleChange(event.target.value)}
                placeholder="Acme Inc"
                value={field.state.value}
              />
              <FieldDescription>
                Use letters, numbers, spaces, hyphens, and underscores only •
                You can always change this later
              </FieldDescription>
              <FieldError errors={field.state.meta.errors} />
            </Field>
          )}
        </form.Field>
      </form>
    </CreateOrganizationDialogLayout>
  );
}

export { OrganizationNameStep };
export type { OrganizationNameFormOutput };
