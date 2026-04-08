import { SourceConnectionAuthFields } from './source-connection-auth-fields';
import { SelectionCard } from './selection-card';
import {
  getAuthMethodForVariant,
  getAvailableAuthMethods,
  getDefaultAuthVariantForMethod,
  getDefaultAuthenticationValues,
  withSourceConnectionForm,
} from './source-connection-form-hook';
import type { Source } from '@/shared/api';
import type {
  SourceConnectionAuthMethod,
  SourceConnectionFormInput,
} from './source-connection-form-hook';
import { Field, FieldTitle } from '@/shared/ui/field';
import { RadioGroup, RadioGroupItem } from '@/shared/ui/radio-group';

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
      return <SourceConnectionAuthFields form={form} source={source} />;
    }

    return (
      <form.Subscribe selector={(state) => state.values.authVariant}>
        {(selectedAuthVariant) => {
          const selectedAuthMethod =
            getAuthMethodForVariant(selectedAuthVariant);

          return (
            <form.Field name="authVariant">
              {(field) => (
                <RadioGroup
                  className="gap-3"
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
                      <SelectionCard
                        key={method}
                        header={
                          <Field orientation="horizontal">
                            <RadioGroupItem id={radioId} value={method} />
                            <FieldTitle>{authMethodLabels[method]}</FieldTitle>
                          </Field>
                        }
                        headerClassName="items-center"
                        htmlFor={radioId}
                        selected={selected}
                      >
                        <SourceConnectionAuthFields
                          form={form}
                          source={source}
                        />
                      </SelectionCard>
                    );
                  })}
                </RadioGroup>
              )}
            </form.Field>
          );
        }}
      </form.Subscribe>
    );
  },
});
