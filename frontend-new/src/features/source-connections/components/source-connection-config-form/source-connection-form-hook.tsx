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
import type { SourceConnectionAuthProviderOption } from '../../lib/source-connection-auth-provider-options';
import {
  getDefaultConfigFieldsValues,
  getDynamicFieldsSchema,
} from '@/shared/config-fields';
import {
  optionalTrimmedStringSchema,
  trimmedStringSchema,
} from '@/shared/forms/schema';

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

function getAuthProviderAuthenticationSchema(
  authProviderOptions: Array<SourceConnectionAuthProviderOption>,
) {
  return z
    .object({
      provider_readable_id: trimmedStringSchema.min(1, 'Provider is required'),
      provider_config: z.record(z.string(), z.unknown()),
    })
    .superRefine((value, ctx) => {
      const selectedOption = authProviderOptions.find(
        (option) => option.readableId === value.provider_readable_id,
      );

      if (!selectedOption) {
        ctx.addIssue({
          code: 'custom',
          message: 'Provider is required',
          path: ['provider_readable_id'],
        });
        return;
      }

      const validationResult = getDynamicFieldsSchema(
        selectedOption.configFields,
      ).safeParse(value.provider_config);

      if (!validationResult.success) {
        for (const issue of validationResult.error.issues) {
          ctx.addIssue({
            ...issue,
            path: ['provider_config', ...issue.path],
          });
        }
      }
    });
}

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

export function getSourceConnectionFormSchema({
  authProviderOptions = [],
  source,
}: {
  authProviderOptions?: Array<SourceConnectionAuthProviderOption>;
  source: Source;
}) {
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
    authentication: getAuthProviderAuthenticationSchema(authProviderOptions),
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
  authProviderOptions = [],
  formSchema,
  source,
}: {
  authProviderOptions?: Array<SourceConnectionAuthProviderOption>;
  formSchema: SourceConnectionFormSchema;
  source: Source;
}) {
  const defaultAuthVariant = getDefaultAuthVariant(source, authProviderOptions);

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

export function getAvailableAuthMethods(
  source: Source,
  authProviderOptions: Array<SourceConnectionAuthProviderOption> = [],
) {
  const methods = new Set(
    (source.auth_methods ?? [])
      .map((method) => normalizeAuthMethod(method))
      .filter((method): method is SourceConnectionAuthMethod => method != null),
  );

  if (methods.has('oauth_browser')) {
    methods.delete('oauth_token');
  }

  if (authProviderOptions.length === 0) {
    methods.delete('auth_provider');
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

function getDefaultAuthMethod(
  source: Source,
  authProviderOptions: Array<SourceConnectionAuthProviderOption> = [],
): SourceConnectionAuthMethod {
  const methods = getAvailableAuthMethods(source, authProviderOptions);

  return methods[0] ?? 'direct';
}

export function getDefaultAuthVariant(
  source: Source,
  authProviderOptions: Array<SourceConnectionAuthProviderOption> = [],
): SourceConnectionAuthVariant {
  return getDefaultAuthVariantForMethod(
    getDefaultAuthMethod(source, authProviderOptions),
    source,
  );
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

export function isOAuth1Source(source: Source) {
  return source.oauth_type === 'oauth1';
}

export function sourceRequiresRefreshToken(source: Source) {
  return (
    source.oauth_type === 'with_refresh' ||
    source.oauth_type === 'with_rotating_refresh'
  );
}
