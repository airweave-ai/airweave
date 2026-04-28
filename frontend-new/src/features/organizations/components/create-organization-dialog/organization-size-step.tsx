import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import { IconCircleCheck } from '@tabler/icons-react';
import * as z from 'zod';
import { CreateOrganizationDialogLayout } from './create-organization-dialog-layout';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { Field, FieldError } from '@/shared/ui/field';

const organizationSizeSchema = z.string().min(1, 'Select an organization size');

const organizationSizeFormSchema = z.object({
  organizationSize: organizationSizeSchema,
});

type OrganizationSizeFormInput = z.input<typeof organizationSizeFormSchema>;
type OrganizationSizeFormOutput = z.output<typeof organizationSizeFormSchema>;

const organizationSizeOptions = [
  { description: 'Solo', label: '1', value: '1' },
  { description: 'Small team', label: '2-5', value: '2-5' },
  { description: 'Growing Startup', label: '6-20', value: '6-20' },
  { description: 'Scale-up', label: '21-100', value: '21-100' },
  { description: 'Mid-market', label: '101-500', value: '101-500' },
  { description: 'Enterprise', label: '500+', value: '500+' },
] as const;

interface OrganizationSizeStepProps {
  defaultValue?: OrganizationSizeFormInput;
  isPending: boolean;
  onCancel: () => void;
  onSubmit: (value: OrganizationSizeFormOutput) => void | Promise<void>;
}

function OrganizationSizeStep({
  defaultValue,
  isPending,
  onCancel,
  onSubmit,
}: OrganizationSizeStepProps) {
  const formId = React.useId();
  const form = useForm({
    defaultValues: defaultValue ?? {
      organizationSize: '',
    },
    validators: {
      onSubmit: organizationSizeFormSchema,
      onChange: organizationSizeFormSchema,
    },
    onSubmit: async ({ value }) => {
      const values = organizationSizeFormSchema.parse(value);

      await onSubmit(values);
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
      <form.Subscribe selector={(state) => state.values.organizationSize}>
        {(organizationSize) => (
          <Button
            className="w-full sm:w-100"
            disabled={isPending || !organizationSize}
            form={formId}
            type="submit"
          >
            {isPending ? 'Creating...' : 'Complete Setup'}
            {!isPending && <IconCircleCheck className="size-4" />}
          </Button>
        )}
      </form.Subscribe>
    </>
  );

  return (
    <CreateOrganizationDialogLayout
      description="This helps us recommend the right plan"
      footer={footer}
      onClose={onCancel}
      step="organization-size"
      title="How many people are in your organization?"
    >
      <form
        className="grid gap-4"
        id={formId}
        onSubmit={(event) => {
          event.preventDefault();
          void form.handleSubmit();
        }}
      >
        <form.Field name="organizationSize">
          {(field) => (
            <Field data-invalid={!field.state.meta.isValid}>
              <div className="mx-auto grid w-full max-w-230 grid-cols-1 gap-2 sm:grid-cols-3">
                {organizationSizeOptions.map((option) => {
                  const selected = field.state.value === option.value;

                  return (
                    <button
                      key={option.value}
                      className={cn(
                        'flex min-h-24 flex-col items-center justify-center gap-1 rounded-md border border-border bg-muted/30 p-4 text-center transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                        selected && 'border-ring bg-muted',
                      )}
                      disabled={isPending}
                      onClick={() => field.handleChange(option.value)}
                      type="button"
                    >
                      <span className="text-lg font-medium">
                        {option.label}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        {option.description}
                      </span>
                    </button>
                  );
                })}
              </div>
              <FieldError errors={field.state.meta.errors} />
            </Field>
          )}
        </form.Field>
      </form>
    </CreateOrganizationDialogLayout>
  );
}

export { OrganizationSizeStep };
export type { OrganizationSizeFormOutput };
