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
  getSourceConnectionFormOptions,
  getSourceConnectionFormSchema,
  useSourceConnectionForm,
} from './source-connection-form-hook';
import { SourceConnectionTextInput } from './source-connection-text-input';
import { SourceConnectionProgress } from './source-connection-progress';
import type { SourceConnectionFormOutput } from './source-connection-form-hook';
import type { SourceConnectionAuthProviderOption } from '../../lib/source-connection-auth-provider-options';
import type { Source } from '@/shared/api';
import { FieldError, FieldGroup } from '@/shared/ui/field';

interface SourceConnectionConfigFormProps {
  authProviderOptions?: Array<SourceConnectionAuthProviderOption>;
  onBack: () => void;
  onSubmit: (values: SourceConnectionFormOutput) => Promise<void> | void;
  source: Source;
  submitError?: string;
}

export function SourceConnectionConfigForm({
  authProviderOptions = [],
  onBack,
  onSubmit,
  source,
  submitError,
}: SourceConnectionConfigFormProps) {
  const formSchema = React.useMemo(
    () => getSourceConnectionFormSchema({ authProviderOptions, source }),
    [authProviderOptions, source],
  );
  const sourceConnectionFormOptions = React.useMemo(
    () =>
      getSourceConnectionFormOptions({
        authProviderOptions,
        formSchema,
        source,
      }),
    [authProviderOptions, formSchema, source],
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
          <SourceConnectionAuthSection
            authProviderOptions={authProviderOptions}
            form={form}
            source={source}
          />
          <SourceConnectionConfigSection form={form} source={source} />
        </form>
      </ConnectSourceStepLayoutContent>

      <div className="shrink-0 space-y-2">
        {submitError ? <FieldError>{submitError}</FieldError> : null}

        <form.Subscribe
          selector={(state) => ({
            isSubmitting: state.isSubmitting,
          })}
        >
          {({ isSubmitting }) => {
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
