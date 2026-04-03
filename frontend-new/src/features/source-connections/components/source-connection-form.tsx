import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import {
  getAuthMethodLabel,
  getAvailableAuthMethods,
  getDefaultAuthMethod,
  hasSourceConnectionFormErrors,
  validateSourceConnectionForm,
} from '../utils';
import { SourceConnectionAuthProviderForm } from './source-connection-auth-provider-form';
import { SourceConnectionDirectForm } from './source-connection-direct-form';
import { SourceConnectionOAuthBrowserForm } from './source-connection-oauth-browser-form';
import { SourceConnectionOAuthTokenForm } from './source-connection-oauth-token-form';
import { SourceFields } from './source-fields';
import type {
  SourceConnectionAuthMethod,
  SourceConnectionFormErrors,
  SourceConnectionFormValues,
} from '../types';
import type { ConfigField, Source } from '@/shared/api';
import { parseApiErrorWithDetail } from '@/shared/api';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import {
  Field,
  FieldContent,
  FieldError,
  FieldGroup,
  FieldTitle,
} from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';
import { Spinner } from '@/shared/ui/spinner';

interface SourceConnectionFormProps {
  footerStart?: React.ReactNode;
  isSubmitting?: boolean;
  onSubmit: (values: SourceConnectionFormValues) => Promise<void> | void;
  source: Source;
}

const defaultFormErrors: SourceConnectionFormErrors = {
  authentication: {},
  config: {},
};

const defaultFormValues: SourceConnectionFormValues = {
  authMethod: 'direct',
  authentication: {
    credentials: {},
  },
  config: {},
  name: '',
};

export function SourceConnectionForm({
  footerStart,
  isSubmitting: isSubmittingProp = false,
  onSubmit,
  source,
}: SourceConnectionFormProps) {
  const [submitErrors, setSubmitErrors] = React.useState(defaultFormErrors);

  const form = useForm({
    defaultValues: defaultFormValues,
    onSubmit: async ({ value }) => {
      const nextErrors = validateSourceConnectionForm({
        authMethod: value.authMethod,
        configFields: source.config_fields.fields,
        source,
        values: value,
      });

      if (hasSourceConnectionFormErrors(nextErrors)) {
        setSubmitErrors(nextErrors);
        return;
      }

      try {
        await onSubmit(value);
        setSubmitErrors(defaultFormErrors);
      } catch (error) {
        setSubmitErrors({
          ...defaultFormErrors,
          form: getSubmitErrorMessage(error),
        });
      }
    },
  });

  React.useEffect(() => {
    const availableAuthMethods = getAvailableAuthMethods(source);
    const currentAuthMethod = form.state.values.authMethod;

    if (!availableAuthMethods.includes(currentAuthMethod)) {
      form.setFieldValue('authMethod', getDefaultAuthMethod(source));
    }
  }, [form, source]);

  const authFields = source.auth_fields?.fields ?? [];
  const availableAuthMethods = getAvailableAuthMethods(source);

  return (
    <form
      className="space-y-6"
      onSubmit={(event) => {
        event.preventDefault();
        void form.handleSubmit();
      }}
    >
      <FieldGroup>
        <form.Field name="name">
          {(field) => (
            <Field>
              <FieldContent>
                <FieldTitle>Name your connection</FieldTitle>
              </FieldContent>
              <Input
                id="source-connection-name"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(event) => {
                  clearFormError(setSubmitErrors);
                  field.handleChange(event.target.value);
                }}
              />
            </Field>
          )}
        </form.Field>
      </FieldGroup>

      {source.config_fields.fields.length > 0 ? (
        <section className="space-y-3">
          <div className="space-y-1">
            <h4 className="text-sm font-medium text-foreground">
              Configuration
            </h4>
            <p className="text-sm text-muted-foreground">
              Source-specific options applied to this connection.
            </p>
          </div>

          <form.Field name="config">
            {(field) => (
              <SourceFields
                errors={submitErrors.config}
                fields={source.config_fields.fields}
                onChange={(fieldName, value) => {
                  setSubmitErrors((currentErrors) => ({
                    ...currentErrors,
                    form: undefined,
                    config: omitError(currentErrors.config, fieldName),
                  }));
                  field.handleChange({
                    ...field.state.value,
                    [fieldName]: value,
                  });
                }}
                values={field.state.value}
              />
            )}
          </form.Field>
        </section>
      ) : null}

      <form.Field name="authMethod">
        {(authMethodField) => {
          const authMethod = authMethodField.state.value;

          return (
            <section className="space-y-3">
              <div className="space-y-1">
                <h4 className="text-sm font-medium text-foreground">
                  Authentication
                </h4>
                <p className="text-sm text-muted-foreground">
                  Choose how this source connection should authenticate.
                </p>
              </div>

              {availableAuthMethods.length > 1 ? (
                <div className="flex flex-wrap gap-2">
                  {availableAuthMethods.map((method) => (
                    <Button
                      key={method}
                      type="button"
                      variant={authMethod === method ? 'default' : 'outline'}
                      onClick={() => {
                        setSubmitErrors((currentErrors) => ({
                          ...currentErrors,
                          authentication: {},
                          form: undefined,
                        }));
                        authMethodField.handleChange(method);
                      }}
                    >
                      {getAuthMethodLabel(method)}
                    </Button>
                  ))}
                </div>
              ) : null}

              <form.Field name="authentication">
                {(authenticationField) =>
                  renderAuthMethodSection({
                    authFields,
                    authMethod,
                    errors: submitErrors.authentication,
                    onChange: (fieldName, value) => {
                      setSubmitErrors((currentErrors) => ({
                        ...currentErrors,
                        form: undefined,
                        authentication: omitError(
                          currentErrors.authentication,
                          fieldName,
                        ),
                      }));

                      authenticationField.handleChange({
                        ...authenticationField.state.value,
                        credentials: {
                          ...(authenticationField.state.value.credentials ??
                            {}),
                          [fieldName]: value,
                        },
                      });
                    },
                    source,
                    values: authenticationField.state.value.credentials ?? {},
                  })
                }
              </form.Field>
            </section>
          );
        }}
      </form.Field>

      <FieldError>{submitErrors.form}</FieldError>

      <form.Subscribe
        selector={(state) => ({
          authMethod: state.values.authMethod,
          isSubmitting: state.isSubmitting,
        })}
      >
        {({ authMethod, isSubmitting }) => {
          const isPending = isSubmitting || isSubmittingProp;

          return (
            <div
              className={cn(
                'flex flex-col gap-2 sm:flex-row',
                footerStart ? 'sm:justify-between' : 'sm:justify-end',
              )}
            >
              {footerStart ? (
                <div className="flex flex-col gap-2 sm:flex-row">
                  {footerStart}
                </div>
              ) : null}
              <Button
                type="submit"
                disabled={isPending || authMethod !== 'direct'}
              >
                {isPending ? <Spinner className="size-4" /> : null}
                Create Connection
              </Button>
            </div>
          );
        }}
      </form.Subscribe>
    </form>
  );
}

function getSubmitErrorMessage(error: unknown) {
  const parsedError = parseApiErrorWithDetail(error);

  if (parsedError?.detail) {
    return parsedError.detail;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return 'Could not create source connection.';
}

function clearFormError(
  setSubmitErrors: React.Dispatch<
    React.SetStateAction<SourceConnectionFormErrors>
  >,
) {
  setSubmitErrors((currentErrors) => ({
    ...currentErrors,
    form: undefined,
  }));
}

function renderAuthMethodSection({
  authFields,
  authMethod,
  errors,
  onChange,
  source,
  values,
}: {
  authFields: Array<ConfigField>;
  authMethod: SourceConnectionAuthMethod;
  errors: Record<string, string>;
  onChange: (fieldName: string, value: unknown) => void;
  source: Source;
  values: Record<string, unknown>;
}) {
  switch (authMethod) {
    case 'direct':
      return (
        <SourceConnectionDirectForm
          authFields={authFields}
          errors={errors}
          onChange={onChange}
          source={source}
          values={values}
        />
      );
    case 'oauth_browser':
      return <SourceConnectionOAuthBrowserForm />;
    case 'oauth_token':
      return <SourceConnectionOAuthTokenForm />;
    case 'auth_provider':
      return <SourceConnectionAuthProviderForm />;
  }
}

function omitError(errors: Record<string, string>, fieldName: string) {
  return Object.fromEntries(
    Object.entries(errors).filter(([key]) => key !== fieldName),
  );
}
