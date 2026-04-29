import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import * as z from 'zod';
import { AccountFormCard } from './account-form-card';
import type { AppSessionViewer } from '@/shared/session';
import { trimmedStringSchema } from '@/shared/forms/schema';
import { Button } from '@/shared/ui/button';
import { Field, FieldError } from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';

const MAX_NAME_LENGTH = 32;

const usernameFormSchema = z.object({
  name: trimmedStringSchema
    .min(1, 'Display name is required.')
    .max(
      MAX_NAME_LENGTH,
      `Display name must be ${MAX_NAME_LENGTH} characters or less.`,
    ),
});

type UsernameFormInput = z.input<typeof usernameFormSchema>;

type UsernameFormProps = {
  viewer: Pick<AppSessionViewer, 'name'>;
};

function UsernameForm({ viewer }: UsernameFormProps) {
  const defaultValues = React.useMemo<UsernameFormInput>(
    () => ({ name: viewer.name ?? '' }),
    [viewer.name],
  );

  const form = useForm({
    defaultValues,
    validators: {
      onSubmit: usernameFormSchema,
    },
    // TODO: Wire this form once the backend exposes a current-user update endpoint.
    onSubmit: () => {},
  });

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void form.handleSubmit();
      }}
    >
      <AccountFormCard
        title="Display name"
        description="Enter your full name or a display name you'd like to use."
        footer={
          <>
            <p className="text-sm text-muted-foreground">
              Maximum allowed length is {MAX_NAME_LENGTH} characters.
            </p>

            <Button type="submit" variant="secondary" size="lg" disabled>
              Save Changes
            </Button>
          </>
        }
      >
        <form.Field name="name">
          {(field) => (
            <Field data-invalid={!field.state.meta.isValid}>
              <Input
                aria-invalid={!field.state.meta.isValid}
                className="max-w-80"
                disabled
                id={field.name}
                maxLength={MAX_NAME_LENGTH}
                onBlur={field.handleBlur}
                onChange={(event) => field.handleChange(event.target.value)}
                placeholder="Enter your display name"
                value={field.state.value}
              />
              <FieldError errors={field.state.meta.errors} />
            </Field>
          )}
        </form.Field>
      </AccountFormCard>
    </form>
  );
}

export { UsernameForm };
