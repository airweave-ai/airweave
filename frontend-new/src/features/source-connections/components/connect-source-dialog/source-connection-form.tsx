import * as React from 'react';
import * as z from 'zod';
import { formOptions, useForm } from '@tanstack/react-form';
import { IconArrowRight } from '@tabler/icons-react';
import { useCreateSourceConnectionMutation } from '../../api';
import { SourceIcon } from '../source-icon';
import { ConfigFieldInput, FormField } from './config-field-input';
import type { SourceConnectionAuthMethod } from '../../types';
import type {
  AuthProviderAuthentication,
  ConfigField,
  DirectAuthentication,
  Source,
  SourceConnection,
  SourceConnectionCreate,
} from '@/shared/api';
import { parseApiErrorWithDetail } from '@/shared/api';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldTitle,
} from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';
import { Spinner } from '@/shared/ui/spinner';
import { RadioGroup, RadioGroupItem } from '@/shared/ui/radio-group';
import { Switch } from '@/shared/ui/switch';

interface SourceConnectionFormProps {
  onSourceConnectionCreated: (source: SourceConnection) => Promise<void> | void;
  collectionId: string;
  source: Source;
  onBack: () => void;
}

const trimmedStringSchema = z.string().trim();
const optionalTrimmedStringSchema = z
  .string()
  .optional()
  .transform((value) => {
    const trimmedValue = value?.trim();

    return trimmedValue === '' ? undefined : trimmedValue;
  });

const oauthBrowserBaseAuthenticationSchema = z.object({
  redirect_uri: optionalTrimmedStringSchema,
});

const oauthBrowserManagedAuthenticationSchema =
  oauthBrowserBaseAuthenticationSchema;

const oauthBrowserOAuth2AuthenticationSchema =
  oauthBrowserBaseAuthenticationSchema.extend({
    client_id: trimmedStringSchema.min(1, 'Client ID is required'),
    client_secret: trimmedStringSchema.min(1, 'Client secret is required'),
  });

const oauthBrowserOAuth1AuthenticationSchema =
  oauthBrowserBaseAuthenticationSchema.extend({
    consumer_key: trimmedStringSchema.min(1, 'Consumer key is required'),
    consumer_secret: trimmedStringSchema.min(1, 'Consumer secret is required'),
  });

const authProviderAuthenticationSchema = z.object({
  provider_readable_id: trimmedStringSchema.min(1, 'Provider is required'),
  // TODO: make provider_config dynamic, based on provider selected
  provider_config: z.record(z.string(), z.unknown()),
});

type AuthVariant =
  | 'direct'
  | 'oauth_browser_managed'
  | 'oauth_browser_custom'
  | 'oauth_token'
  | 'auth_provider';

function getSourceConnectionFormSchema({ source }: { source: Source }) {
  const configSchema = getDynamicFieldsSchema(source.config_fields.fields);
  const credentialsSchema = source.auth_fields
    ? getDynamicFieldsSchema(source.auth_fields.fields)
    : z.record(z.string(), z.unknown());

  const commonFormSchema = z.object({
    name: trimmedStringSchema.min(1, 'Name is required'),
    config: configSchema,
  });

  const directSchema = commonFormSchema.extend({
    authVariant: z.literal('direct'),
    authentication: z.object({
      credentials: credentialsSchema,
    }),
  });

  const oauthTokenSchema = commonFormSchema.extend({
    authVariant: z.literal('oauth_token'),
    authentication: getOAuthTokenAuthenticationSchema(source),
  });

  const authProviderSchema = commonFormSchema.extend({
    authVariant: z.literal('auth_provider'),
    authentication: authProviderAuthenticationSchema,
  });

  const oauthBrowserCustomSchema = commonFormSchema.extend({
    authVariant: z.literal('oauth_browser_custom'),
    authentication: getOAuthBrowserCustomAuthenticationSchema(source),
  });

  if (source.requires_byoc) {
    return z.discriminatedUnion('authVariant', [
      directSchema,
      oauthTokenSchema,
      authProviderSchema,
      oauthBrowserCustomSchema,
    ]);
  }

  const oauthBrowserManagedSchema = commonFormSchema.extend({
    authVariant: z.literal('oauth_browser_managed'),
    authentication: oauthBrowserManagedAuthenticationSchema,
  });

  return z.discriminatedUnion('authVariant', [
    directSchema,
    oauthTokenSchema,
    authProviderSchema,
    oauthBrowserManagedSchema,
    oauthBrowserCustomSchema,
  ]);
}

type SourceConnectionFormSchema = ReturnType<
  typeof getSourceConnectionFormSchema
>;
type SourceConnectionFormInput = z.input<SourceConnectionFormSchema>;
type SourceConnectionFormOutput = z.output<SourceConnectionFormSchema>;

function getOAuthTokenAuthenticationSchema(source: Source) {
  return z.object({
    access_token: trimmedStringSchema.min(1, 'Access token is required'),
    refresh_token: sourceRequiresRefreshToken(source)
      ? trimmedStringSchema.min(1, 'Refresh token is required')
      : optionalTrimmedStringSchema,
    expires_at: optionalTrimmedStringSchema,
  });
}

function getOAuthBrowserCustomAuthenticationSchema(source: Source) {
  return isOAuth1Source(source)
    ? oauthBrowserOAuth1AuthenticationSchema
    : oauthBrowserOAuth2AuthenticationSchema;
}

function getSourceConnectionFormOptions({
  formSchema,
  source,
}: {
  formSchema: SourceConnectionFormSchema;
  source: Source;
  configuredAuthProviders: Array<string>;
}) {
  const defaultAuthVariant = getDefaultAuthVariant(source);

  return formOptions({
    defaultValues: {
      authVariant: defaultAuthVariant,
      name: `${source.name} Connection`,
      authentication: getDefaultAuthenticationValues(
        defaultAuthVariant,
        source,
        source.auth_fields?.fields,
      ),
      config: getDefaultConfigFieldsValues(source.config_fields.fields),
    } as SourceConnectionFormInput,
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
        : optionalTrimmedStringSchema;
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
  authVariant: AuthVariant,
  source: Source,
  authFields: Array<ConfigField> | undefined,
  redirectUri?: string,
): SourceConnectionFormInput['authentication'] {
  if (authVariant === 'direct') {
    return {
      credentials: getDefaultConfigFieldsValues(authFields),
    } satisfies DirectAuthentication;
  }
  if (authVariant === 'oauth_token') {
    return {
      access_token: '',
      refresh_token: sourceRequiresRefreshToken(source) ? '' : undefined,
      expires_at: undefined,
    };
  }
  if (authVariant === 'oauth_browser_managed') {
    return {
      redirect_uri: redirectUri,
    };
  }
  if (authVariant === 'oauth_browser_custom') {
    if (isOAuth1Source(source)) {
      return {
        redirect_uri: redirectUri,
        consumer_key: '',
        consumer_secret: '',
      };
    }

    return {
      redirect_uri: redirectUri,
      client_id: '',
      client_secret: '',
    };
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
  const formSchema = React.useMemo(
    () => getSourceConnectionFormSchema({ source }),
    [source],
  );
  const sourceConnectionFormOptions = React.useMemo(
    () =>
      getSourceConnectionFormOptions({
        formSchema,
        source,
        configuredAuthProviders: [],
      }),
    [formSchema, source],
  );

  const form = useForm({
    ...sourceConnectionFormOptions,
    onSubmit: async ({ value }) => {
      const parsedValue = formSchema.parse(value);
      const sourceConnection = await createSourceConnectionMutation.mutateAsync(
        {
          body: buildSourceConnectionPayload({
            source,
            readableCollectionId: collectionId,
            values: parsedValue,
          }),
        },
      );
      return onSourceConnectionCreated(sourceConnection);
    },
  });

  const availableAuthMethods = getAvailableAuthMethods(source);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex justify-between gap-3 pb-6">
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
            <a
              href={`https://docs.airweave.ai/docs/connectors/${source.short_name.replace(/_/g, '-')}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-sm font-normal text-muted-foreground hover:underline"
            >
              See Docs
            </a>
          </div>
        </div>
        <form.Subscribe selector={(state) => state.values.authVariant}>
          {(selectedAuthVariant) => {
            const selectedAuthMethod =
              getAuthMethodForVariant(selectedAuthVariant);
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
        className="flex min-h-0 flex-1 flex-col"
        onSubmit={(event) => {
          event.preventDefault();
          void form.handleSubmit();
        }}
      >
        <div className="mb-6 min-h-0 flex-1 space-y-6 overflow-y-auto">
          <FieldGroup>
            <form.Field name="name">
              {(field) => {
                return (
                  <SourceConnectionTextInput
                    errors={field.state.meta.errors}
                    id={field.name}
                    onBlur={field.handleBlur}
                    onChange={field.handleChange}
                    required
                    title="Name your connection"
                    value={field.state.value}
                  />
                );
              }}
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

          <section className="space-y-3">
            <form.Field name="authVariant">
              {(field) => {
                return availableAuthMethods.length > 1 ? (
                  <RadioGroup
                    key="auth-method-selector"
                    value={getAuthMethodForVariant(field.state.value)}
                    onValueChange={(method: SourceConnectionAuthMethod) => {
                      const nextAuthVariant = getDefaultAuthVariantForMethod(
                        method,
                        source,
                      );

                      field.handleChange(nextAuthVariant);
                      form.setFieldValue(
                        'authentication',
                        getDefaultAuthenticationValues(
                          nextAuthVariant,
                          source,
                          source.auth_fields?.fields,
                        ),
                      );
                    }}
                  >
                    {availableAuthMethods.map((method) => (
                      <FieldLabel key={method}>
                        <Field orientation="horizontal">
                          <RadioGroupItem value={method} />
                          <FieldTitle>{authMethodLabels[method]}</FieldTitle>
                        </Field>
                      </FieldLabel>
                    ))}
                  </RadioGroup>
                ) : null;
              }}
            </form.Field>

            <form.Subscribe
              selector={(state) => ({
                authVariant: state.values.authVariant,
                authentication: state.values.authentication,
              })}
            >
              {({ authVariant, authentication }) => {
                const selectedAuthMethod = getAuthMethodForVariant(authVariant);

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

                if (selectedAuthMethod === 'oauth_browser') {
                  const oauthCredentialTitles = isOAuth1Source(source)
                    ? {
                        key: 'Consumer Key',
                        secret: 'Consumer Secret',
                      }
                    : {
                        key: 'Client ID',
                        secret: 'Client Secret',
                      };

                  return (
                    <React.Fragment key="oauth-browser-inputs">
                      <form.Field name="authentication.redirect_uri">
                        {(field) => (
                          <SourceConnectionTextInput
                            description="Optional callback URL override. Leave empty to use the default Airweave redirect."
                            errors={field.state.meta.errors}
                            id={field.name}
                            onBlur={field.handleBlur}
                            onChange={field.handleChange}
                            title="Redirect URI"
                            value={field.state.value ?? ''}
                          />
                        )}
                      </form.Field>

                      {source.requires_byoc ? (
                        <div className="space-y-1 rounded-lg border border-border bg-muted/30 p-3">
                          <p className="text-sm font-medium text-foreground">
                            Custom OAuth credentials required
                          </p>
                          <FieldDescription>
                            {source.name} requires your own OAuth application
                            credentials for browser auth.
                          </FieldDescription>
                        </div>
                      ) : (
                        <Field orientation="responsive">
                          <FieldLabel htmlFor="use-custom-oauth-credentials">
                            Use custom OAuth credentials
                          </FieldLabel>
                          <Switch
                            checked={authVariant === 'oauth_browser_custom'}
                            id="use-custom-oauth-credentials"
                            onCheckedChange={(checked) => {
                              const nextAuthVariant = checked
                                ? 'oauth_browser_custom'
                                : 'oauth_browser_managed';

                              form.setFieldValue(
                                'authVariant',
                                nextAuthVariant,
                              );
                              form.setFieldValue(
                                'authentication',
                                getDefaultAuthenticationValues(
                                  nextAuthVariant,
                                  source,
                                  source.auth_fields?.fields,
                                  getRedirectUri(authentication),
                                ),
                              );
                            }}
                          />
                          <FieldDescription>
                            By default Airweave uses its managed OAuth app.
                            Enable this to use your own{' '}
                            {oauthCredentialTitles.key.toLowerCase()} and{' '}
                            {oauthCredentialTitles.secret.toLowerCase()}.
                          </FieldDescription>
                        </Field>
                      )}

                      {authVariant === 'oauth_browser_custom' ? (
                        <React.Fragment>
                          <form.Field
                            name={
                              isOAuth1Source(source)
                                ? 'authentication.consumer_key'
                                : 'authentication.client_id'
                            }
                          >
                            {(field) => (
                              <SourceConnectionTextInput
                                description={`OAuth ${oauthCredentialTitles.key.toLowerCase()} for your application.`}
                                errors={field.state.meta.errors}
                                id={field.name}
                                onBlur={field.handleBlur}
                                onChange={field.handleChange}
                                required
                                title={oauthCredentialTitles.key}
                                value={field.state.value}
                              />
                            )}
                          </form.Field>

                          <form.Field
                            name={
                              isOAuth1Source(source)
                                ? 'authentication.consumer_secret'
                                : 'authentication.client_secret'
                            }
                          >
                            {(field) => (
                              <SourceConnectionTextInput
                                description={`OAuth ${oauthCredentialTitles.secret.toLowerCase()} for your application.`}
                                errors={field.state.meta.errors}
                                id={field.name}
                                onBlur={field.handleBlur}
                                onChange={field.handleChange}
                                required
                                title={oauthCredentialTitles.secret}
                                type="password"
                                value={field.state.value}
                              />
                            )}
                          </form.Field>
                        </React.Fragment>
                      ) : null}
                    </React.Fragment>
                  );
                }

                if (selectedAuthMethod === 'oauth_token') {
                  return (
                    <React.Fragment key="oauth-token-inputs">
                      <form.Field name="authentication.access_token">
                        {(field) => (
                          <SourceConnectionTextInput
                            description="OAuth access token to use for this connection."
                            errors={field.state.meta.errors}
                            id={field.name}
                            onBlur={field.handleBlur}
                            onChange={field.handleChange}
                            required
                            title="Access Token"
                            type="password"
                            value={field.state.value}
                          />
                        )}
                      </form.Field>

                      {source.oauth_type !== 'access_only' ? (
                        <form.Field name="authentication.refresh_token">
                          {(field) => (
                            <SourceConnectionTextInput
                              description={
                                sourceRequiresRefreshToken(source)
                                  ? 'Refresh token used to renew the access token.'
                                  : 'Optional refresh token used to renew the access token.'
                              }
                              errors={field.state.meta.errors}
                              id={field.name}
                              onBlur={field.handleBlur}
                              onChange={field.handleChange}
                              required={sourceRequiresRefreshToken(source)}
                              title="Refresh Token"
                              type="password"
                              value={field.state.value ?? ''}
                            />
                          )}
                        </form.Field>
                      ) : null}

                      <form.Field name="authentication.expires_at">
                        {(field) => (
                          <SourceConnectionTextInput
                            description="Optional ISO 8601 expiry timestamp for the access token."
                            errors={field.state.meta.errors}
                            id={field.name}
                            onBlur={field.handleBlur}
                            onChange={field.handleChange}
                            title="Expires At"
                            value={field.state.value ?? ''}
                          />
                        )}
                      </form.Field>
                    </React.Fragment>
                  );
                }

                return (
                  <div className="rounded-lg border border-dashed border-border p-3 text-sm text-muted-foreground">
                    Auth provider configuration is not implemented yet.
                  </div>
                );
              }}
            </form.Subscribe>
          </section>
        </div>

        <div className="shrink-0">
          {createSourceConnectionMutation.error && (
            <FieldError>
              {getSubmitErrorMessage(createSourceConnectionMutation.error)}
            </FieldError>
          )}

          <form.Subscribe
            selector={(state) => ({
              authVariant: state.values.authVariant,
              isSubmitting: state.isSubmitting,
            })}
          >
            {({ authVariant, isSubmitting }) => {
              const authMethod = getAuthMethodForVariant(authVariant);

              return (
                <div
                  className={cn(
                    'flex flex-col gap-2 sm:flex-row sm:justify-between',
                  )}
                >
                  <Button
                    type="button"
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
                    disabled={isSubmitting || authMethod === 'auth_provider'}
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
        </div>
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

const SUPPORTED_AUTH_METHODS: Array<SourceConnectionAuthMethod> = [
  'oauth_browser',
  'oauth_token',
  'direct',
  'auth_provider',
];

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
  const methods = new Set(
    (source.auth_methods ?? [])
      .map((method) => normalizeAuthMethod(method))
      .filter((method): method is SourceConnectionAuthMethod => method != null),
  );

  if (methods.has('oauth_browser')) {
    methods.delete('oauth_token');
  }

  return SUPPORTED_AUTH_METHODS.filter((method) => methods.has(method));
}

function getAuthMethodForVariant(
  authVariant: AuthVariant,
): SourceConnectionAuthMethod {
  if (
    authVariant === 'oauth_browser_managed' ||
    authVariant === 'oauth_browser_custom'
  ) {
    return 'oauth_browser';
  }

  return authVariant;
}

function getDefaultAuthMethod(source: Source): SourceConnectionAuthMethod {
  const methods = getAvailableAuthMethods(source);

  return methods[0] ?? 'direct';
}

function getDefaultAuthVariant(source: Source): AuthVariant {
  return getDefaultAuthVariantForMethod(getDefaultAuthMethod(source), source);
}

function getDefaultAuthVariantForMethod(
  authMethod: SourceConnectionAuthMethod,
  source: Source,
): AuthVariant {
  if (authMethod !== 'oauth_browser') {
    return authMethod;
  }

  return source.requires_byoc
    ? 'oauth_browser_custom'
    : 'oauth_browser_managed';
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
  direct: 'Direct Credentials',
  oauth_browser: 'OAuth Connection',
  oauth_token: 'OAuth Connection',
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
  authVariant,
  source,
}: {
  authVariant: AuthVariant;
  source: Source;
}) {
  if (source.supports_browse_tree) {
    return false;
  }

  return getAuthMethodForVariant(authVariant) !== 'oauth_browser';
}

function isOAuth1Source(source: Source) {
  return source.oauth_type === 'oauth1';
}

function sourceRequiresRefreshToken(source: Source) {
  return (
    source.oauth_type === 'with_refresh' ||
    source.oauth_type === 'with_rotating_refresh'
  );
}

function getRedirectUri(
  authentication: SourceConnectionFormInput['authentication'],
) {
  return 'redirect_uri' in authentication
    ? authentication.redirect_uri
    : undefined;
}

function buildSourceConnectionPayload({
  readableCollectionId,
  source,
  values,
}: {
  readableCollectionId: string;
  source: Source;
  values: SourceConnectionFormOutput;
}): SourceConnectionCreate {
  const syncImmediately = getSyncImmediately({
    authVariant: values.authVariant,
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

function SourceConnectionTextInput({
  description,
  errors,
  id,
  onBlur,
  onChange,
  required,
  title,
  type = 'text',
  value,
}: {
  description?: string;
  errors?: Array<{ message?: string } | undefined>;
  id: string;
  onBlur?: React.FocusEventHandler<HTMLInputElement>;
  onChange: (value: string) => void;
  required?: boolean;
  title: string;
  type?: React.HTMLInputTypeAttribute;
  value: string;
}) {
  const hasErrors = Boolean(errors?.length);

  return (
    <FormField
      description={description}
      errors={errors}
      name={id}
      required={required}
      title={title}
    >
      <Input
        aria-invalid={hasErrors}
        id={id}
        onBlur={onBlur}
        onChange={(event) => onChange(event.target.value)}
        type={type}
        value={value}
      />
    </FormField>
  );
}
