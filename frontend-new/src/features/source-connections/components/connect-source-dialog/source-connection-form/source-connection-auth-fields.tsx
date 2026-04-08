import * as React from 'react';
import { ConfigFieldInput } from './config-field-input';
import { SourceConnectionTextInput } from './source-connection-text-input';
import {
  getAuthMethodForVariant,
  getDefaultAuthenticationValues,
  isOAuth1Source,
  isSupportedConfigFieldType,
  sourceRequiresRefreshToken,
  withSourceConnectionForm,
} from './source-connection-form-hook';
import type { SourceConnectionFormInput } from './source-connection-form-hook';
import type { Source } from '@/shared/api';
import { Field, FieldDescription, FieldLabel } from '@/shared/ui/field';
import { Switch } from '@/shared/ui/switch';

function getRedirectUri(authentication: SourceConnectionFormInput['authentication']) {
  return 'redirect_uri' in authentication
    ? authentication.redirect_uri
    : undefined;
}

export const SourceConnectionAuthFields = withSourceConnectionForm({
  defaultValues: {} as SourceConnectionFormInput,
  props: {
    source: undefined as unknown as Source,
  },
  render: ({ form, source }) => {
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
                      <ConfigFieldInput
                        description={authField.description ?? undefined}
                        errors={field.state.meta.errors}
                        fieldType={
                          isSupportedConfigFieldType(authField.type)
                            ? authField.type
                            : 'string'
                        }
                        name={field.name}
                        onBlur={field.handleBlur}
                        onChange={field.handleChange}
                        required={authField.required}
                        title={authField.title}
                        value={(field.state.value ?? '') as any}
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
              <React.Fragment>
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
                      {source.name} requires your own OAuth application credentials
                      for browser auth.
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
                    <FieldDescription>
                      By default Airweave uses its managed OAuth app. Enable this
                      to use your own {oauthCredentialTitles.key.toLowerCase()} and{' '}
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

          return (
            <div className="rounded-lg border border-dashed border-border p-3 text-sm text-muted-foreground">
              Auth provider configuration is not implemented yet.
            </div>
          );
        }}
      </form.Subscribe>
    );
  },
});
