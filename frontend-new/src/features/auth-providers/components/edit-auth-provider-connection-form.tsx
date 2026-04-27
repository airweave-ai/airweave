import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import * as z from 'zod';
import { AuthProviderSettingsLink } from './auth-provider-settings-link';
import type {
  AuthProviderConnection,
  AuthProviderMetadata,
  ConfigField,
} from '@/shared/api';
import {
  DynamicConfigFieldInput,
  FormField,
  getDynamicFieldsSchema,
} from '@/shared/config-fields';
import { trimmedStringSchema } from '@/shared/forms/schema';
import { FieldError, FieldGroup } from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';

type EditAuthProviderConnectionFormProps = {
  authProvider: AuthProviderMetadata;
  connection: AuthProviderConnection;
  formId: string;
  isPending?: boolean;
  onSubmit: (
    values: EditAuthProviderConnectionFormOutput,
  ) => Promise<void> | void;
  onValueChange?: () => void;
  submitError?: string;
};

export type EditAuthProviderConnectionFormSchema = ReturnType<
  typeof getEditAuthProviderConnectionFormSchema
>;
export type EditAuthProviderConnectionFormInput =
  z.input<EditAuthProviderConnectionFormSchema>;
export type EditAuthProviderConnectionFormOutput =
  z.output<EditAuthProviderConnectionFormSchema>;

export function EditAuthProviderConnectionForm({
  authProvider,
  connection,
  formId,
  isPending,
  onSubmit,
  onValueChange,
  submitError,
}: EditAuthProviderConnectionFormProps) {
  const formSchema = React.useMemo(
    () => getEditAuthProviderConnectionFormSchema(authProvider),
    [authProvider],
  );
  const defaultValues = React.useMemo<EditAuthProviderConnectionFormInput>(
    () => ({
      auth_fields: undefined,
      name: connection.name,
    }),
    [connection.name],
  );
  const authFields = authProvider.auth_fields?.fields ?? [];

  const form = useForm({
    defaultValues,
    validators: {
      onSubmit: formSchema,
    },
    onSubmit: async ({ value }) => {
      return onSubmit(formSchema.parse(value));
    },
  });

  return (
    <form
      className="grid gap-4"
      id={formId}
      onSubmit={(event) => {
        event.preventDefault();
        void form.handleSubmit();
      }}
    >
      <FieldGroup className="gap-4">
        <form.Field name="name">
          {(field) => (
            <FormField
              disabled={isPending}
              errors={field.state.meta.errors}
              name={field.name}
              required
              title="Name"
            >
              <Input
                aria-invalid={!field.state.meta.isValid}
                autoFocus
                disabled={isPending}
                id={field.name}
                onBlur={field.handleBlur}
                onChange={(event) => {
                  onValueChange?.();
                  field.handleChange(event.target.value);
                }}
                placeholder="My Connection"
                value={field.state.value}
              />
            </FormField>
          )}
        </form.Field>

        {authFields.map((authField) => {
          return (
            <form.Field
              key={authField.name}
              name={`auth_fields.${authField.name}`}
            >
              {(field) => (
                <DynamicConfigFieldInput
                  configField={authField}
                  disabled={isPending}
                  errors={field.state.meta.errors}
                  name={field.name}
                  onBlur={field.handleBlur}
                  onChange={(value) => {
                    onValueChange?.();
                    field.handleChange(value);
                  }}
                  placeholder={getAuthFieldPlaceholder(authField)}
                  required={false}
                  value={field.state.value}
                />
              )}
            </form.Field>
          );
        })}

        {authFields.length > 0 ? (
          <AuthProviderSettingsLink shortName={authProvider.short_name} />
        ) : null}
      </FieldGroup>

      {submitError ? <FieldError>{submitError}</FieldError> : null}
    </form>
  );
}

function getEditAuthProviderConnectionFormSchema(
  authProvider: AuthProviderMetadata,
) {
  return z.object({
    auth_fields: getOptionalAuthFieldsSchema(
      authProvider.auth_fields?.fields ?? [],
    ),
    name: trimmedStringSchema.min(1, 'Name is required'),
  });
}

function getOptionalAuthFieldsSchema(fields: Array<ConfigField>) {
  return z.preprocess((value) => {
    if (isEmptyAuthFieldsValue(value)) {
      return undefined;
    }

    return value;
  }, getDynamicFieldsSchema(fields).optional());
}

function isEmptyAuthFieldsValue(value: unknown) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return true;
  }

  return Object.values(value).every((fieldValue) => {
    if (fieldValue === undefined || fieldValue === null) {
      return true;
    }

    if (typeof fieldValue === 'string') {
      return fieldValue.trim() === '';
    }

    if (Array.isArray(fieldValue)) {
      return fieldValue.length === 0;
    }

    return false;
  });
}

function getAuthFieldPlaceholder(authField: ConfigField) {
  return `Enter your ${authField.title}`;
}
