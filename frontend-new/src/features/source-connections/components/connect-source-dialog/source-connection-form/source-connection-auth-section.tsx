import { SourceConnectionAuthFields } from './source-connection-auth-fields';
import {
  getAuthMethodForVariant,
  getAvailableAuthMethods,
  getDefaultAuthVariantForMethod,
  getDefaultAuthenticationValues,
  withSourceConnectionForm,
} from './source-connection-form-hook';
import type { SourceConnectionAuthMethod } from '../../../types';
import type { Source } from '@/shared/api';
import type { SourceConnectionFormInput } from './source-connection-form-hook';
import { cn } from '@/shared/tailwind/cn';
import { Field, FieldTitle } from '@/shared/ui/field';
import { RadioGroup, RadioGroupItem } from '@/shared/ui/radio-group';
import { Label } from '@/shared/ui/label';

const authMethodLabels = {
  direct: 'Direct Credentials',
  oauth_browser: 'OAuth Connection',
  oauth_token: 'OAuth Connection',
  auth_provider: 'Auth Provider',
} satisfies Record<SourceConnectionAuthMethod, string>;

export const SourceConnectionAuthSection = withSourceConnectionForm({
  defaultValues: {} as SourceConnectionFormInput,
  props: {
    source: undefined as unknown as Source,
  },
  render: ({ form, source }) => {
    const availableAuthMethods = getAvailableAuthMethods(source);

    if (availableAuthMethods.length === 1) {
      return (
        <section className="space-y-3">
          <SourceConnectionAuthFields form={form} source={source} />
        </section>
      );
    }

    return (
      <form.Subscribe selector={(state) => state.values.authVariant}>
        {(selectedAuthVariant) => {
          const selectedAuthMethod =
            getAuthMethodForVariant(selectedAuthVariant);

          return (
            <section className="space-y-3">
              <form.Field name="authVariant">
                {(field) => (
                  <RadioGroup
                    className="space-y-3"
                    key="auth-method-selector"
                    value={selectedAuthMethod}
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
                    {availableAuthMethods.map((method) => {
                      const selected = selectedAuthMethod === method;
                      const radioId = `auth-method-${method}`;

                      return (
                        <div
                          key={method}
                          className={cn(
                            'rounded-lg border transition-colors',
                            selected
                              ? 'border-foreground/30 bg-muted/40'
                              : 'border-border',
                          )}
                        >
                          <Label
                            className="flex cursor-pointer items-center gap-3 p-4"
                            htmlFor={radioId}
                          >
                            <Field orientation="horizontal">
                              <RadioGroupItem id={radioId} value={method} />
                              <FieldTitle>
                                {authMethodLabels[method]}
                              </FieldTitle>
                            </Field>
                          </Label>

                          {selected ? (
                            <div className="mt-4 space-y-3 px-4 pb-4">
                              <SourceConnectionAuthFields
                                form={form}
                                source={source}
                              />
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </RadioGroup>
                )}
              </form.Field>
            </section>
          );
        }}
      </form.Subscribe>
    );
  },
});
