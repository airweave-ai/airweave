import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import { IconArrowRight, IconPlayerStopFilled } from '@tabler/icons-react';
import * as z from 'zod';
import { useClassicCollectionSearchMutation } from '../../api';
import { CollectionSearchState } from './collection-search-state';
import { getApiErrorMessage } from '@/shared/api';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from '@/shared/ui/input-group';

const collectionSearchQuerySchema = z
  .string()
  .trim()
  .min(1, 'Ask a question to search this collection.');

const collectionSearchFormSchema = z.object({
  query: collectionSearchQuerySchema,
});

const defaultFormValues = {
  query: '',
};

export function CollectionSearch({
  collectionId,
  disabled = false,
}: {
  collectionId: string;
  disabled?: boolean;
}) {
  const classicSearchMutation = useClassicCollectionSearchMutation();
  const requestAbort = useAbortController();
  const isPending = classicSearchMutation.isPending;
  const isSuccess = classicSearchMutation.isSuccess;
  const response = classicSearchMutation.data;
  const resultsCount = response?.results?.length ?? 0;
  const submitError = isAbortError(classicSearchMutation.error)
    ? undefined
    : getApiErrorMessage(
        classicSearchMutation.error,
        'Search failed. Try again.',
      );

  const form = useForm({
    defaultValues: defaultFormValues,
    validators: {
      onChange: collectionSearchFormSchema,
      onMount: collectionSearchFormSchema,
      onSubmit: collectionSearchFormSchema,
    },
    onSubmit: ({ value }) => {
      const { query } = collectionSearchFormSchema.parse(value);
      const abortController = requestAbort.next();

      classicSearchMutation.mutate(
        {
          body: { query },
          path: { readable_id: collectionId },
          signal: abortController.signal,
        },
        {
          onSettled: () => {
            requestAbort.clear(abortController);
          },
        },
      );
    },
  });

  const handleSubmit = React.useCallback(() => {
    void form.handleSubmit();
  }, [form]);

  const handleCancel = React.useCallback(() => {
    requestAbort.abort();
  }, [requestAbort]);

  return (
    <div className="px-4">
      <div className="space-y-3">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            handleSubmit();
          }}
        >
          <div className="space-y-2">
            <InputGroup className="rounded-sm border-none">
              <form.Field name="query">
                {(field) => {
                  const query = field.state.value;

                  return (
                    <InputGroupTextarea
                      disabled={disabled}
                      placeholder="Ask your agent a question..."
                      value={query}
                      className="min-h-21 px-4 pt-4 pb-2 text-sm leading-5 placeholder:text-muted-foreground"
                      onBlur={field.handleBlur}
                      onChange={(event) => {
                        if (classicSearchMutation.error) {
                          classicSearchMutation.reset();
                        }

                        field.handleChange(event.target.value);
                      }}
                      onKeyDown={(event) => {
                        if (
                          event.key !== 'Enter' ||
                          event.shiftKey ||
                          event.nativeEvent.isComposing
                        ) {
                          return;
                        }

                        event.preventDefault();

                        if (!disabled && !isPending && form.state.canSubmit) {
                          handleSubmit();
                        }
                      }}
                    />
                  );
                }}
              </form.Field>

              <InputGroupAddon
                align="block-end"
                className="w-full items-center justify-between gap-3"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <div className="inline-flex h-7 items-center rounded-sm bg-background/60 px-2.5 font-mono text-xs font-medium text-foreground/80 ring-1 ring-foreground/10">
                    Classic
                  </div>
                </div>

                <form.Subscribe selector={(state) => state.canSubmit}>
                  {(canSubmit) => {
                    const buttonClassName = 'size-9 rounded-xs';

                    if (isPending) {
                      return (
                        <InputGroupButton
                          aria-label="Cancel search"
                          disabled={disabled}
                          size="icon-sm"
                          type="button"
                          variant="destructive"
                          className={buttonClassName}
                          onClick={handleCancel}
                        >
                          <IconPlayerStopFilled className="size-4" />
                        </InputGroupButton>
                      );
                    }

                    return (
                      <InputGroupButton
                        aria-label="Search collection"
                        disabled={disabled || !canSubmit}
                        size="icon-sm"
                        type="submit"
                        variant="default"
                        className={buttonClassName}
                      >
                        <IconArrowRight className="size-4" />
                      </InputGroupButton>
                    );
                  }}
                </form.Subscribe>
              </InputGroupAddon>
            </InputGroup>
          </div>
        </form>

        <CollectionSearchState
          isPending={isPending}
          isSuccess={isSuccess}
          response={response}
          resultsCount={resultsCount}
          submitError={submitError}
        />
      </div>
    </div>
  );
}

function useAbortController() {
  const controllerRef = React.useRef<AbortController | null>(null);

  React.useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  const next = React.useCallback(() => {
    controllerRef.current?.abort();

    const controller = new AbortController();
    controllerRef.current = controller;

    return controller;
  }, []);

  const abort = React.useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  const clear = React.useCallback((controller: AbortController) => {
    if (controllerRef.current === controller) {
      controllerRef.current = null;
    }
  }, []);

  return { abort, clear, next };
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}
