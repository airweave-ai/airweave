import * as React from 'react';
import { IconArrowRight } from '@tabler/icons-react';
import {
  ConnectSourceBackActionButton,
  ConnectSourcePrimaryActionButton,
  ConnectSourceStepLayoutActions,
  ConnectSourceStepLayoutContent,
} from '../connect-source-step-layout';
import { SourceConnectionHeader } from '../source-connection-header';
import { SourceConnectionAuthSection } from './source-connection-auth-section';
import { SourceConnectionConfigSection } from './source-connection-config-section';
import {
  getAuthMethodForVariant,
  getSourceConnectionFormOptions,
  getSourceConnectionFormSchema,
  useSourceConnectionForm,
} from './source-connection-form-hook';
import { SourceConnectionTextInput } from './source-connection-text-input';
import { SourceConnectionProgress } from './source-connection-progress';
import type { SourceConnectionFormOutput } from './source-connection-form-hook';
import type { Source } from '@/shared/api';
import { FieldError, FieldGroup } from '@/shared/ui/field';

interface SourceConnectionConfigFormProps {
  onBack: () => void;
  onSubmit: (values: SourceConnectionFormOutput) => Promise<void> | void;
  source: Source;
  submitError?: string;
}

export function SourceConnectionConfigForm({
  onBack,
  onSubmit,
  source,
  submitError,
}: SourceConnectionConfigFormProps) {
  const formSchema = React.useMemo(
    () => getSourceConnectionFormSchema({ source }),
    [source],
  );
  const sourceConnectionFormOptions = React.useMemo(
    () => getSourceConnectionFormOptions({ formSchema, source }),
    [formSchema, source],
  );
  const formId = React.useId();

  const form = useSourceConnectionForm({
    ...sourceConnectionFormOptions,
    onSubmit: async ({ value }) => {
      return onSubmit(formSchema.parse(value));
    },
  });

  return (
    <div className="flex h-full min-h-0 flex-col gap-6">
      <SourceConnectionHeader
        source={source}
        aside={
          <form.Subscribe selector={(state) => state.values.authVariant}>
            {(selectedAuthVariant) => (
              <SourceConnectionProgress authVariant={selectedAuthVariant} />
            )}
          </form.Subscribe>
        }
      />
      <ConnectSourceStepLayoutContent asChild>
        <form
          id={formId}
          onSubmit={(event) => {
            event.preventDefault();
            void form.handleSubmit();
          }}
        >
          <FieldGroup>
            <form.Field name="name">
              {(field) => (
                <SourceConnectionTextInput
                  errors={field.state.meta.errors}
                  id={field.name}
                  onBlur={field.handleBlur}
                  onChange={field.handleChange}
                  required
                  title="Name your connection"
                  value={field.state.value}
                />
              )}
            </form.Field>
          </FieldGroup>
          <SourceConnectionAuthSection form={form} source={source} />
          <SourceConnectionConfigSection form={form} source={source} />
        </form>
      </ConnectSourceStepLayoutContent>

      <div className="shrink-0 space-y-2">
        {submitError ? <FieldError>{submitError}</FieldError> : null}

        <form.Subscribe
          selector={(state) => ({
            authVariant: state.values.authVariant,
            isSubmitting: state.isSubmitting,
          })}
        >
          {({ authVariant, isSubmitting }) => {
            const authMethod = getAuthMethodForVariant(authVariant);

            return (
              <ConnectSourceStepLayoutActions
                backAction={
                  <ConnectSourceBackActionButton
                    disabled={isSubmitting}
                    onClick={onBack}
                  >
                    Back
                  </ConnectSourceBackActionButton>
                }
              >
                <ConnectSourcePrimaryActionButton
                  type="submit"
                  form={formId}
                  disabled={authMethod === 'auth_provider'}
                  icon={<IconArrowRight className="size-4" />}
                  isLoading={isSubmitting}
                >
                  Connect with {source.name}
                </ConnectSourcePrimaryActionButton>
              </ConnectSourceStepLayoutActions>
            );
          }}
        </form.Subscribe>
      </div>
    </div>
  );
}
