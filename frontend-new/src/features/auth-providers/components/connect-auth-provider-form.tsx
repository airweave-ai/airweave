import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import { ArrowUpRight } from 'lucide-react';
import * as z from 'zod';
import { generateRandomSuffix, generateReadableId } from '../lib/readable-id';
import type { AuthProviderMetadata, ConfigField } from '@/shared/api';
import type { ConfigFieldValue } from '@/shared/config-fields';
import {
  ConfigFieldInput,
  FormField,
  getDefaultConfigFieldsValues,
  getDefaultValueForConfigFieldType,
  getDynamicFieldsSchema,
  isSupportedConfigFieldType,
} from '@/shared/config-fields';
import {
  optionalTrimmedStringSchema,
  trimmedStringSchema,
} from '@/shared/forms/schema';
import { Button } from '@/shared/ui/button';
import { FieldError, FieldGroup } from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';

const readableIdPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const authProviderSettingsLinks = {
  composio: {
    href: 'https://platform.composio.dev/',
    label: 'Get API Key from Composio',
  },
  pipedream: {
    href: 'https://pipedream.com/settings/api',
    label: 'Get Client ID & Secret from Pipedream',
  },
} as const;

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

  const settingsLink = getAuthProviderSettingsLink(authProvider.short_name);

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
          const fieldType = isSupportedConfigFieldType(authField.type)
            ? authField.type
            : 'string';

          return (
            <form.Field
              key={authField.name}
              name={`auth_fields.${authField.name}`}
            >
              {(field) => (
                <ConfigFieldInput
                  disabled={isPending}
                  errors={field.state.meta.errors}
                  fieldType={fieldType}
                  isSecret={authField.is_secret}
                  name={field.name}
                  onBlur={field.handleBlur}
                  onChange={(value: ConfigFieldValue) => {
                    onValueChange?.();
                    field.handleChange(value);
                  }}
                  placeholder={getAuthFieldPlaceholder(authField)}
                  required={authField.required}
                  title={authField.title}
                  value={
                    (field.state.value ??
                      getDefaultValueForConfigFieldType(authField.type)) as any
                  }
                />
              )}
            </form.Field>
          );
        })}

        {settingsLink !== null && authFields.length > 0 ? (
          <Button asChild className="w-fit" variant="outline">
            <a href={settingsLink.href} rel="noreferrer" target="_blank">
              {settingsLink.label}
              <ArrowUpRight className="size-4" />
            </a>
          </Button>
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

function getAuthProviderSettingsLink(shortName: string) {
  if (!(shortName in authProviderSettingsLinks)) {
    return null;
  }

  return authProviderSettingsLinks[
    shortName as keyof typeof authProviderSettingsLinks
  ];
}
