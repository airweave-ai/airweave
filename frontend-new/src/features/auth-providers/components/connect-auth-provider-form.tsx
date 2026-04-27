import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import * as z from 'zod';
import { generateRandomSuffix, generateReadableId } from '../lib/readable-id';
import { AuthProviderSettingsLink } from './auth-provider-settings-link';
import type { AuthProviderMetadata, ConfigField } from '@/shared/api';
import {
  DynamicConfigFieldInput,
  FormField,
  getDefaultConfigFieldsValues,
  getDynamicFieldsSchema,
} from '@/shared/config-fields';
import {
  optionalTrimmedStringSchema,
  trimmedStringSchema,
} from '@/shared/forms/schema';
import { FieldError, FieldGroup } from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';

const readableIdPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

type ConnectAuthProviderFormProps = {
  authProvider: AuthProviderMetadata;
  formId: string;
  isPending?: boolean;
  onSubmit: (values: ConnectAuthProviderFormOutput) => Promise<void> | void;
  onValueChange?: () => void;
  submitError?: string;
};

export type ConnectAuthProviderFormSchema = ReturnType<
  typeof getConnectAuthProviderFormSchema
>;
export type ConnectAuthProviderFormInput =
  z.input<ConnectAuthProviderFormSchema>;
export type ConnectAuthProviderFormOutput =
  z.output<ConnectAuthProviderFormSchema>;

export function ConnectAuthProviderForm({
  authProvider,
  formId,
  isPending,
  onSubmit,
  onValueChange,
  submitError,
}: ConnectAuthProviderFormProps) {
  const formSchema = React.useMemo(
    () => getConnectAuthProviderFormSchema(authProvider),
    [authProvider],
  );
  const readableIdSuffixRef = React.useRef(generateRandomSuffix());
  const previousNameRef = React.useRef(
    getDefaultConnectionName(authProvider.name),
  );
  const defaultValues = React.useMemo<ConnectAuthProviderFormInput>(() => {
    const defaultName = getDefaultConnectionName(authProvider.name);

    return {
      auth_fields: getDefaultConfigFieldsValues(
        authProvider.auth_fields?.fields,
      ),
      name: defaultName,
      readable_id: generateReadableId(defaultName, readableIdSuffixRef.current),
    };
  }, [authProvider]);
  const [isReadableIdManual, setIsReadableIdManual] =
    React.useState(false);
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
                  const nextName = event.target.value;

                  onValueChange?.();
                  field.handleChange(nextName);

                  if (
                    previousNameRef.current &&
                    nextName === '' &&
                    !isReadableIdManual
                  ) {
                    readableIdSuffixRef.current = generateRandomSuffix();
                  }

                  if (!isReadableIdManual) {
                    form.setFieldValue(
                      'readable_id',
                      generateReadableId(nextName, readableIdSuffixRef.current),
                    );
                  }

                  previousNameRef.current = nextName;
                }}
                placeholder="My Connection"
                value={field.state.value}
              />
            </FormField>
          )}
        </form.Field>

        <form.Field name="readable_id">
          {(field) => (
            <FormField
              disabled={isPending}
              errors={field.state.meta.errors}
              name={field.name}
              title="Readable ID"
            >
              <Input
                aria-invalid={!field.state.meta.isValid}
                disabled={isPending}
                id={field.name}
                onBlur={field.handleBlur}
                onChange={(event) => {
                  const nextReadableId = event.target.value;

                  onValueChange?.();
                  field.handleChange(nextReadableId);

                  if (!form.state.values.name.trim()) {
                    setIsReadableIdManual(true);
                    return;
                  }

                  setIsReadableIdManual(
                    nextReadableId !==
                      generateReadableId(
                        form.state.values.name,
                        readableIdSuffixRef.current,
                      ),
                  );
                }}
                placeholder="Auto-generated"
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

function getConnectAuthProviderFormSchema(authProvider: AuthProviderMetadata) {
  return z.object({
    auth_fields: getDynamicFieldsSchema(authProvider.auth_fields?.fields ?? []),
    name: trimmedStringSchema.min(1, 'Name is required'),
    readable_id: optionalTrimmedStringSchema.refine(
      (value) => value === undefined || readableIdPattern.test(value),
      'Readable ID must contain only lowercase letters, numbers, and hyphens',
    ),
  });
}

function getDefaultConnectionName(authProviderName: string) {
  return `My ${authProviderName} Connection`;
}

function getAuthFieldPlaceholder(authField: ConfigField) {
  return `Enter your ${authField.title}`;
}
