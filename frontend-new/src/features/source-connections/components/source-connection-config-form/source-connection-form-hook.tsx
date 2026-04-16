import * as z from 'zod';
import {
  createFormHook,
  createFormHookContexts,
  formOptions,
} from '@tanstack/react-form';
import type {
  AuthProviderAuthentication,
  AuthenticationMethod,
  ConfigField,
  DirectAuthentication,
  Source,
} from '@/shared/api';

const { fieldContext, formContext, useFieldContext, useFormContext } =
  createFormHookContexts();

export const {
  useAppForm: useSourceConnectionForm,
  withForm: withSourceConnectionForm,
} = createFormHook({
  fieldComponents: {},
  fieldContext,
  formComponents: {},
  formContext,
});

export {
  useFieldContext as useSourceConnectionFieldContext,
  useFormContext as useSourceConnectionFormContext,
};

const trimmedStringSchema = z.string().trim();
const optionalTrimmedStringSchema = z
  .string()
  .optional()
  .transform((value) => {
    const trimmedValue = value?.trim();

    return trimmedValue === '' ? undefined : trimmedValue;
  });

const oauthBrowserBaseAuthenticationSchema = z.object({
  redirect_uri: z
    .url({
      protocol: /^https?$/,
      error: 'Redirect URI must be a valid http:// or https:// URL',
    })
    .optional(),
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
  provider_config: z.record(z.string(), z.unknown()),
});

export type SourceConnectionAuthMethod = Exclude<
  AuthenticationMethod,
  'oauth_byoc'
>;

export type SourceConnectionAuthVariant =
  | 'direct'
  | 'oauth_browser_managed'
  | 'oauth_browser_custom'
  | 'oauth_token'
  | 'auth_provider';

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

export function getSourceConnectionFormSchema({ source }: { source: Source }) {
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

export type SourceConnectionFormSchema = ReturnType<
  typeof getSourceConnectionFormSchema
>;
export type SourceConnectionFormInput = z.input<SourceConnectionFormSchema>;
export type SourceConnectionFormOutput = z.output<SourceConnectionFormSchema>;

export function getSourceConnectionFormOptions({
  formSchema,
  source,
}: {
  formSchema: SourceConnectionFormSchema;
  source: Source;
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

export function getDefaultAuthenticationValues(
  authVariant: SourceConnectionAuthVariant,
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

export function getAvailableAuthMethods(source: Source) {
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

export function getAuthMethodForVariant(
  authVariant: SourceConnectionAuthVariant,
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

export function getDefaultAuthVariant(
  source: Source,
): SourceConnectionAuthVariant {
  return getDefaultAuthVariantForMethod(getDefaultAuthMethod(source), source);
}

export function getDefaultAuthVariantForMethod(
  authMethod: SourceConnectionAuthMethod,
  source: Source,
): SourceConnectionAuthVariant {
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

export function isSupportedConfigFieldType(
  fieldType: string,
): fieldType is SupportedConfigFieldType {
  return SUPPORTED_CONFIG_FIELD_TYPES.includes(
    fieldType as SupportedConfigFieldType,
  );
}

export function isOAuth1Source(source: Source) {
  return source.oauth_type === 'oauth1';
}

export function sourceRequiresRefreshToken(source: Source) {
  return (
    source.oauth_type === 'with_refresh' ||
    source.oauth_type === 'with_rotating_refresh'
  );
}
