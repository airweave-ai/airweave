import * as React from 'react';
import * as z from 'zod';
import { formOptions, useForm } from '@tanstack/react-form';
import { IconArrowRight } from '@tabler/icons-react';
import { useCreateSourceConnectionMutation } from '../../api';
import { SourceIcon } from '../source-icon';
import { ConfigFieldInput } from './config-field-input';
import type { SourceConnectionAuthMethod } from '../../types';
import type {
  AuthProviderAuthentication,
  ConfigField,
  DirectAuthentication,
  OAuthBrowserAuthentication,
  OAuthTokenAuthentication,
  Source,
  SourceConnection,
  SourceConnectionCreate,
} from '@/shared/api';
import { parseApiErrorWithDetail } from '@/shared/api';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { Field, FieldError, FieldGroup, FieldLabel } from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';
import { Spinner } from '@/shared/ui/spinner';

interface SourceConnectionFormProps {
  onSourceConnectionCreated: (source: SourceConnection) => Promise<void> | void;
  collectionId: string;
  source: Source;
  onBack: () => void;
}

const SUPPORTED_AUTH_METHODS: Array<SourceConnectionAuthMethod> = [
  'direct',
  'oauth_browser',
  'oauth_token',
  'auth_provider',
];

const trimmedStringSchema = z.string().trim();

const oauthTokenAuthenticationSchema = z.object({
  access_token: trimmedStringSchema.min(1, 'Access token is required'),
  refresh_token: trimmedStringSchema.optional(),
  expires_at: trimmedStringSchema.optional(),
});

const oauthBrowserAuthenticationSchema = z.object({
  redirect_uri: trimmedStringSchema.optional(),
  client_id: trimmedStringSchema.optional(),
  client_secret: trimmedStringSchema.optional(),
  consumer_key: trimmedStringSchema.optional(),
  consumer_secret: trimmedStringSchema.optional(),
});
const authProviderAuthenticationSchema = z.object({
  provider_readable_id: trimmedStringSchema.min(1, 'Provider is required'),
  // TODO: make provider_config dynamic, based on provider selected
  provider_config: z.record(z.string(), z.unknown()),
});

function getSourceConnectionFormSchema({ source }: { source: Source }) {
  const configSchema = getDynamicFieldsSchema(source.config_fields.fields);
  const credentialsSchema = source.auth_fields
    ? getDynamicFieldsSchema(source.auth_fields.fields)
    : z.record(z.string(), z.unknown());

  const commonFormSchema = z.object({
    name: trimmedStringSchema.min(1, 'Name is required'),
    config: configSchema,
  });

  return z.discriminatedUnion('authMethod', [
    commonFormSchema.extend({
      authMethod: z.literal('direct'),
      authentication: z.object({
        credentials: credentialsSchema,
      }),
    }),
    commonFormSchema.extend({
      authMethod: z.literal('oauth_token'),
      authentication: oauthTokenAuthenticationSchema,
    }),
    commonFormSchema.extend({
      authMethod: z.literal('oauth_browser'),
      authentication: oauthBrowserAuthenticationSchema,
    }),
    commonFormSchema.extend({
      authMethod: z.literal('auth_provider'),
      authentication: authProviderAuthenticationSchema,
    }),
  ]);
}

function getSourceConnectionFormOptions({
  source,
}: {
  source: Source;
  configuredAuthProviders: Array<string>;
}) {
  const formSchema = getSourceConnectionFormSchema({ source });
  const defaultAuthMethod = getDefaultAuthMethod(source);

  return formOptions({
    defaultValues: {
      authMethod: defaultAuthMethod,
      name: `${source.name} Connection`,
      authentication: getDefaultAuthenticationValues(
        defaultAuthMethod,
        source.auth_fields?.fields,
      ),
      config: getDefaultConfigFieldsValues(source.config_fields.fields),
    } as z.infer<typeof formSchema>,
    validators: {
      onSubmit: formSchema,
    },
  });
}

function getDynamicFieldsSchema(fields: Array<ConfigField>) {
  const schema: Record<string, z.ZodType> = {};
  for (const field of fields) {
    schema[field.name] = getDynamicFieldSchema(field);
  }
  return z.object(schema);
}

function getDynamicFieldSchema(field: ConfigField) {
  const fieldType = isSupportedConfigFieldType(field.type)
    ? field.type
    : 'string';

  switch (fieldType) {
    case 'string':
      return field.required
        ? trimmedStringSchema.min(1, `${field.title} is required`)
        : trimmedStringSchema.optional();
    case 'boolean':
      return field.required
        ? z.boolean(`${field.title} is required`)
        : z.boolean().optional();
    case 'number':
      return field.required
        ? z.number(`${field.title} is required`)
        : z.number().optional();
    case 'array': {
      const itemSchema = trimmedStringSchema;
      return field.required
        ? z.array(itemSchema).min(1, `${field.title} is required`)
        : z.array(itemSchema).optional();
    }
    default:
      fieldType satisfies never;
      throw new Error(`Unsupported field.type ${fieldType}`);
  }
}

function getDefaultAuthenticationValues(
  authMethod: SourceConnectionAuthMethod,
  authFields: Array<ConfigField> | undefined,
) {
  if (authMethod === 'direct') {
    return {
      credentials: getDefaultConfigFieldsValues(authFields),
    } satisfies DirectAuthentication;
  }
  if (authMethod === 'oauth_token') {
    return {
      access_token: '',
    } satisfies OAuthTokenAuthentication;
  }
  if (authMethod === 'oauth_browser') {
    return {} satisfies OAuthBrowserAuthentication;
  }
  return {
    provider_readable_id: '',
    provider_config: {},
  } satisfies AuthProviderAuthentication;
}

function getDefaultConfigFieldsValues(
  configFields: Array<ConfigField> | undefined,
) {
  if (!configFields) {
    return {};
  }
  return Object.fromEntries(
    configFields
      .filter((field) => field.required)
      .map((field) => {
        return [field.name, getDefaultValueForConfigFieldType(field.type)];
      }),
  );
}

function getDefaultValueForConfigFieldType(configFieldType: string) {
  const supportedConfigFieldType = isSupportedConfigFieldType(configFieldType)
    ? configFieldType
    : 'string';
  switch (supportedConfigFieldType) {
    case 'string':
      return '';
    case 'number':
      return 0;
    case 'boolean':
      return false;
    case 'array':
      return [] as Array<unknown>;
  }
}

export function SourceConnectionForm({
  collectionId,
  onSourceConnectionCreated,
  source,
  onBack,
}: SourceConnectionFormProps) {
  const createSourceConnectionMutation = useCreateSourceConnectionMutation();

  const form = useForm({
    ...getSourceConnectionFormOptions({ source, configuredAuthProviders: [] }),
    onSubmit: async ({ value }) => {
      const sourceConnection = await createSourceConnectionMutation.mutateAsync(
        {
          body: buildSourceConnectionPayload({
            source,
            readableCollectionId: collectionId,
            values: value,
          }),
        },
      );
      return onSourceConnectionCreated(sourceConnection);
    },
  });

  const availableAuthMethods = getAvailableAuthMethods(source);

  return (
    <div className="flex h-full min-h-0 flex-col gap-6">
      <div className="flex justify-between gap-3">
        <div className="flex gap-3">
          <div className="flex size-10 items-center justify-center rounded-xs border bg-muted">
            <SourceIcon
              className="size-4"
              name={source.name}
              shortName={source.short_name}
            />
          </div>
          <div>
            <h2 className="font-medium">Connect {source.name}</h2>
            <a className="font-mono text-sm font-normal text-muted-foreground">
              See Docs
            </a>
          </div>
        </div>
        <form.Subscribe selector={(state) => state.values.authMethod}>
          {(selectedAuthMethod) => {
            const { step, numberOfSteps, label } =
              authMethodStepLabels[selectedAuthMethod];
            return (
              <span className="font-mono text-sm text-foreground/60">
                Step {step}{' '}
                <span className="text-foreground/40">
                  of {numberOfSteps}: {label}
                </span>
              </span>
            );
          }}
        </form.Subscribe>
      </div>
      <form
        className="space-y-6"
        onSubmit={(event) => {
          event.preventDefault();
          void form.handleSubmit();
        }}
      >
        <FieldGroup>
          <form.Field name="name">
            {(field) => {
              const errors = field.state.meta.errors;
              const hasErrors = Boolean(errors.length);
              return (
                <Field key="name-field" data-invalid={hasErrors}>
                  <FieldLabel htmlFor={field.name}>
                    Name your connection
                  </FieldLabel>
                  <Input
                    id={field.name}
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(e) => field.handleChange(e.target.value)}
                    aria-invalid={hasErrors}
                  />
                  <FieldError errors={field.state.meta.errors} />
                </Field>
              );
            }}
          </form.Field>
        </FieldGroup>

        <section className="space-y-3">
          <div className="space-y-1">
            <h4 className="text-sm font-medium text-foreground">
              Authentication
            </h4>
            <p className="text-sm text-muted-foreground">
              Choose how this source connection should authenticate.
            </p>
          </div>
          <form.Field
            name="authMethod"
            listeners={{
              onChange: ({ value }) => {
                form.setFieldValue(
                  'authentication',
                  getDefaultAuthenticationValues(
                    value,
                    source.auth_fields?.fields,
                  ) as Record<string, unknown>,
                );
              },
            }}
          >
            {(field) => {
              return availableAuthMethods.length > 1 ? (
                <div
                  key="auth-method-selector"
                  className="flex flex-wrap gap-2"
                >
                  {availableAuthMethods.map((method) => (
                    <Button
                      key={method}
                      type="button"
                      variant={
                        field.state.value === method ? 'default' : 'outline'
                      }
                      onClick={() => {
                        field.handleChange(method);
                      }}
                    >
                      {authMethodLabels[method]}
                    </Button>
                  ))}
                </div>
              ) : null;
            }}
          </form.Field>

          <form.Subscribe selector={(state) => state.values.authMethod}>
            {(selectedAuthMethod) => {
              if (selectedAuthMethod === 'direct') {
                const authFields = source.auth_fields?.fields;
                return (
                  <React.Fragment key="direct-auth-inputs">
                    {authFields?.map((authField) => (
                      <form.Field
                        name={`authentication.credentials.${authField.name}`}
                      >
                        {(field) => (
                          <ConfigFieldInput
                            name={field.name}
                            title={authField.title}
                            description={authField.description ?? undefined}
                            required={authField.required}
                            fieldType={
                              isSupportedConfigFieldType(authField.type)
                                ? authField.type
                                : 'string'
                            }
                            onChange={field.handleChange}
                            onBlur={field.handleBlur}
                            value={(field.state.value ?? '') as any}
                            errors={field.state.meta.errors}
                          />
                        )}
                      </form.Field>
                    ))}
                  </React.Fragment>
                );
              }
              // TODO
              return <div>WIP</div>;
            }}
          </form.Subscribe>
        </section>

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

            {source.config_fields.fields.map((configField) => (
              <form.Field name={`config.${configField.name}`}>
                {(field) => (
                  <ConfigFieldInput
                    name={field.name}
                    title={configField.title}
                    description={configField.description ?? undefined}
                    required={configField.required}
                    fieldType={
                      isSupportedConfigFieldType(configField.type)
                        ? configField.type
                        : 'string'
                    }
                    onChange={field.handleChange}
                    onBlur={field.handleBlur}
                    value={(field.state.value ?? '') as any}
                    errors={field.state.meta.errors}
                  />
                )}
              </form.Field>
            ))}
          </section>
        ) : null}

        {createSourceConnectionMutation.error && (
          <FieldError>
            {getSubmitErrorMessage(createSourceConnectionMutation.error)}
          </FieldError>
        )}

        <form.Subscribe
          selector={(state) => ({
            authMethod: state.values.authMethod,
            isSubmitting: state.isSubmitting,
          })}
        >
          {({ authMethod, isSubmitting }) => {
            return (
              <div
                className={cn(
                  'flex flex-col gap-2 sm:flex-row sm:justify-between',
                )}
              >
                <Button
                  size="lg"
                  className="max-w-55 flex-1"
                  disabled={isSubmitting}
                  variant="ghost"
                  onClick={onBack}
                >
                  Back
                </Button>
                <Button
                  type="submit"
                  size="lg"
                  className="max-w-130 flex-1"
                  disabled={isSubmitting || authMethod !== 'direct'}
                >
                  Connect with {source.name}{' '}
                  {isSubmitting ? (
                    <Spinner className="size-4" />
                  ) : (
                    <IconArrowRight className="size-4" />
                  )}
                </Button>
              </div>
            );
          }}
        </form.Subscribe>
      </form>
    </div>
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

function normalizeAuthMethod(
  authMethod: string | null | undefined,
): SourceConnectionAuthMethod | null {
  if (authMethod === 'oauth_byoc') {
    return 'oauth_browser';
  }

  return SUPPORTED_AUTH_METHODS.includes(
    authMethod as SourceConnectionAuthMethod,
  )
    ? (authMethod as SourceConnectionAuthMethod)
    : null;
}

function getAvailableAuthMethods(source: Source) {
  const methods = (source.auth_methods ?? [])
    .map((method) => normalizeAuthMethod(method))
    .filter((method): method is SourceConnectionAuthMethod => method != null);

  return Array.from(new Set(methods));
}

function getDefaultAuthMethod(source: Source): SourceConnectionAuthMethod {
  const methods = getAvailableAuthMethods(source);

  return methods[0] ?? 'direct';
}

const SUPPORTED_CONFIG_FIELD_TYPES = [
  'string',
  'number',
  'boolean',
  'array',
] as const;
type SupportedConfigFieldType = (typeof SUPPORTED_CONFIG_FIELD_TYPES)[number];

function isSupportedConfigFieldType(
  fieldType: string,
): fieldType is SupportedConfigFieldType {
  return SUPPORTED_CONFIG_FIELD_TYPES.includes(
    fieldType as SupportedConfigFieldType,
  );
}

const authMethodLabels = {
  direct: 'Direct',
  oauth_browser: 'OAuth Browser',
  oauth_token: 'OAuth Token',
  auth_provider: 'Auth Provider',
} satisfies Record<SourceConnectionAuthMethod, string>;

const authMethodStepLabels = {
  direct: {
    step: 2,
    numberOfSteps: 2,
    label: 'Enter Token',
  },
  oauth_browser: {
    step: 1,
    numberOfSteps: 2,
    label: 'Configure',
  },
  oauth_token: {
    step: 2,
    numberOfSteps: 2,
    label: 'Enter Token',
  },
  auth_provider: {
    step: 2,
    numberOfSteps: 2,
    label: 'Configure',
  },
} satisfies Record<
  SourceConnectionAuthMethod,
  { step: number; numberOfSteps: number; label: string }
>;

function getSyncImmediately({
  authMethod,
  source,
}: {
  authMethod: SourceConnectionAuthMethod;
  source: Source;
}) {
  if (source.supports_browse_tree) {
    return false;
  }

  return authMethod !== 'oauth_browser';
}

function buildSourceConnectionPayload({
  readableCollectionId,
  source,
  values,
}: {
  readableCollectionId: string;
  source: Source;
  values: z.infer<ReturnType<typeof getSourceConnectionFormSchema>>;
}): SourceConnectionCreate {
  const syncImmediately = getSyncImmediately({
    authMethod: values.authMethod,
    source,
  });

  return {
    config: values.config,
    name: values.name,
    readable_collection_id: readableCollectionId,
    short_name: source.short_name,
    sync_immediately: syncImmediately,
    authentication: values.authentication,
  };
}
