import * as React from 'react';
import { IconArrowRight } from '@tabler/icons-react';
import { SourceIcon } from '../source-icon';
import { SourceConnectionAuthSection } from './source-connection-auth-section';
import { SourceConnectionConfigSection } from './source-connection-config-section';
import { getSourceDocsUrl } from './source-docs-url';
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
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { FieldError, FieldGroup } from '@/shared/ui/field';
import { Spinner } from '@/shared/ui/spinner';

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

  const form = useSourceConnectionForm({
    ...sourceConnectionFormOptions,
    onSubmit: async ({ value }) => {
      return onSubmit(formSchema.parse(value));
    },
  });

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
              href={getSourceDocsUrl(source.short_name)}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-sm font-normal text-muted-foreground hover:underline"
            >
              See Docs
            </a>
          </div>
        </div>
        <form.Subscribe selector={(state) => state.values.authVariant}>
          {(selectedAuthVariant) => (
            <SourceConnectionProgress authVariant={selectedAuthVariant} />
          )}
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
        </div>

        <div className="shrink-0">
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
