import * as React from 'react';
import { IconInfoCircle } from '@tabler/icons-react';
import { getSourceDocsUrl } from '../../lib/source-docs-url';
import { SelectionCard } from './selection-card';
import { SourceConnectionTextInput } from './source-connection-text-input';
import {
  getAuthMethodForVariant,
  getDefaultAuthenticationValues,
  isOAuth1Source,
  sourceRequiresRefreshToken,
  withSourceConnectionForm,
} from './source-connection-form-hook';
import type { SourceConnectionFormInput } from './source-connection-form-hook';
import type { SourceConnectionAuthProviderOption } from '../../lib/source-connection-auth-provider-options';
import type { Source } from '@/shared/api';
import { AuthProviderIcon } from '@/shared/components/auth-provider-icon';
import {
  DynamicConfigFieldInput,
  getDefaultConfigFieldsValues,
} from '@/shared/config-fields';
import { Button } from '@/shared/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert';
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
  FieldLegend,
  FieldSet,
  FieldTitle,
} from '@/shared/ui/field';
import { Input } from '@/shared/ui/input';
import { RadioGroup, RadioGroupItem } from '@/shared/ui/radio-group';
import { Separator } from '@/shared/ui/separator';
import { Switch } from '@/shared/ui/switch';

function getRedirectUri(
  authentication: SourceConnectionFormInput['authentication'],
) {
  return 'redirect_uri' in authentication
    ? authentication.redirect_uri
    : undefined;
}

export const SourceConnectionAuthFields = withSourceConnectionForm({
  defaultValues: {} as SourceConnectionFormInput,
  props: {
    authProviderOptions: [] as Array<SourceConnectionAuthProviderOption>,
    source: undefined as unknown as Source,
  },
  render: ({ authProviderOptions, form, source }) => {
    return (
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
              <React.Fragment>
                {authFields?.map((authField) => (
                  <form.Field
                    key={authField.name}
                    name={`authentication.credentials.${authField.name}`}
                  >
                    {(field) => (
                      <DynamicConfigFieldInput
                        configField={authField}
                        disabled={form.state.isSubmitting}
                        errors={field.state.meta.errors}
                        name={field.name}
                        onBlur={field.handleBlur}
                        onChange={field.handleChange}
                        value={field.state.value}
                      />
                    )}
                  </form.Field>
                ))}
              </React.Fragment>
            );
          }

          if (selectedAuthMethod === 'oauth_browser') {
            const redirectUri = getRedirectUri(authentication);
            const hasCustomRedirectUri = redirectUri !== undefined;
            const oauthCredentialTitles = isOAuth1Source(source)
              ? {
                  key: 'Consumer Key',
                  secret: 'Consumer Secret',
                }
              : {
                  key: 'Client ID',
                  secret: 'Client Secret',
                };
            const sourceDocsUrl = getSourceDocsUrl(source.short_name);
            const customOAuthCredentialFields = (
              <div className="grid grid-cols-2 gap-3">
                <form.Field
                  name={
                    isOAuth1Source(source)
                      ? 'authentication.consumer_key'
                      : 'authentication.client_id'
                  }
                >
                  {(field) => (
                    <SourceConnectionTextInput
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
              </div>
            );

            return (
              <React.Fragment>
                {source.requires_byoc ? (
                  <Alert className="gap-y-3 p-4">
                    <IconInfoCircle className="size-4" />
                    <div className="col-start-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="space-y-0.5">
                        <AlertTitle>OAuth Needed</AlertTitle>
                        <AlertDescription>
                          {source.name} requires you to provide your own OAuth
                          application credentials. You'll need to create an
                          OAuth app in {source.name}'s developer console.
                        </AlertDescription>
                      </div>
                      <Button
                        asChild
                        className="shrink-0"
                        size="sm"
                        variant="outline"
                      >
                        <a
                          href={sourceDocsUrl}
                          rel="noopener noreferrer"
                          target="_blank"
                        >
                          See Documentation
                        </a>
                      </Button>
                    </div>
                    <div className="col-span-full">
                      {customOAuthCredentialFields}
                    </div>
                  </Alert>
                ) : (
                  <SelectionCard
                    header={
                      <React.Fragment>
                        <div className="space-y-1">
                          <FieldTitle>Use custom OAuth credentials</FieldTitle>
                          <FieldDescription className="text-balance">
                            By default, Airweave handles OAuth for you.
                            <br />
                            Enable this to use your own OAuth app, with your own
                            name and logo.
                          </FieldDescription>
                        </div>
                        <Switch
                          checked={authVariant === 'oauth_browser_custom'}
                          id="use-custom-oauth-credentials"
                          onCheckedChange={(checked) => {
                            const nextAuthVariant = checked
                              ? 'oauth_browser_custom'
                              : 'oauth_browser_managed';

                            form.setFieldValue('authVariant', nextAuthVariant);
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
                      </React.Fragment>
                    }
                    headerClassName="items-start justify-between"
                    htmlFor="use-custom-oauth-credentials"
                    selected={authVariant === 'oauth_browser_custom'}
                  >
                    {customOAuthCredentialFields}
                  </SelectionCard>
                )}

                <Separator />

                <form.Field name="authentication.redirect_uri">
                  {(field) => {
                    const hasErrors = !field.state.meta.isValid;

                    return (
                      <div className="space-y-2">
                        <div className="flex items-start justify-between gap-3">
                          <FieldLabel htmlFor={field.name}>
                            {hasCustomRedirectUri
                              ? 'Custom OAuth callback URL'
                              : 'OAuth callback URL'}
                          </FieldLabel>

                          <Button
                            type="button"
                            variant="link"
                            className="h-5"
                            onClick={() => {
                              field.handleChange(
                                hasCustomRedirectUri ? undefined : '',
                              );
                            }}
                          >
                            {hasCustomRedirectUri
                              ? 'Use default'
                              : 'Use custom URL'}
                          </Button>
                        </div>

                        <Input
                          aria-invalid={hasErrors}
                          disabled={!hasCustomRedirectUri}
                          id={field.name}
                          onBlur={field.handleBlur}
                          onChange={(event) =>
                            field.handleChange(event.target.value)
                          }
                          placeholder={
                            hasCustomRedirectUri
                              ? 'https://your-app.com/integrations/callback'
                              : 'Default (managed by Airweave)'
                          }
                          value={
                            hasCustomRedirectUri
                              ? (field.state.value ?? '')
                              : ''
                          }
                        />

                        <FieldDescription className="text-balance">
                          {hasCustomRedirectUri
                            ? 'Must exactly match the redirect URL in your provider app settings. You are responsible for handling this callback.'
                            : 'After authorization, providers redirect here so Airweave can finish the connection.'}
                        </FieldDescription>

                        <FieldError errors={field.state.meta.errors} />
                      </div>
                    );
                  }}
                </form.Field>
              </React.Fragment>
            );
          }

          if (selectedAuthMethod === 'oauth_token') {
            return (
              <React.Fragment>
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

          if (authProviderOptions.length === 0) {
            return (
              <FieldSet>
                <FieldLegend variant="label">
                  Use your auth provider
                </FieldLegend>
                <FieldDescription>
                  No matching auth provider connections are available.
                </FieldDescription>
              </FieldSet>
            );
          }

          return (
            <form.Field name="authentication.provider_readable_id">
              {(field) => {
                const selectedOption = authProviderOptions.find(
                  (option) => option.readableId === field.state.value,
                );

                return (
                  <FieldSet>
                    <FieldLegend variant="label">
                      Use your auth provider
                    </FieldLegend>

                    <RadioGroup
                      orientation="horizontal"
                      className="grid-cols-3"
                      value={field.state.value}
                      onValueChange={(readableId) => {
                        const nextOption = authProviderOptions.find(
                          (option) => option.readableId === readableId,
                        );

                        form.setFieldValue('authentication', {
                          provider_readable_id: readableId,
                          provider_config: getDefaultConfigFieldsValues(
                            nextOption?.configFields,
                          ),
                        });
                      }}
                    >
                      {authProviderOptions.map((option) => {
                        const radioId = `auth-provider-${option.readableId}`;

                        return (
                          <FieldLabel key={option.readableId}>
                            <Field orientation="horizontal">
                              <RadioGroupItem
                                id={radioId}
                                value={option.readableId}
                              />
                              <AuthProviderIcon
                                className="size-5 shrink-0"
                                name={option.providerName}
                                shortName={option.providerShortName}
                              />
                              {option.connectionName}
                            </Field>
                          </FieldLabel>
                        );
                      })}
                    </RadioGroup>

                    <FieldError errors={field.state.meta.errors} />

                    {selectedOption?.configFields.map((configField) => (
                      <form.Field
                        key={configField.name}
                        name={`authentication.provider_config.${configField.name}`}
                      >
                        {(configFieldFormField) => (
                          <DynamicConfigFieldInput
                            configField={configField}
                            disabled={form.state.isSubmitting}
                            errors={configFieldFormField.state.meta.errors}
                            name={configFieldFormField.name}
                            onBlur={configFieldFormField.handleBlur}
                            onChange={configFieldFormField.handleChange}
                            value={configFieldFormField.state.value}
                          />
                        )}
                      </form.Field>
                    ))}
                  </FieldSet>
                );
              }}
            </form.Field>
          );
        }}
      </form.Subscribe>
    );
  },
});
