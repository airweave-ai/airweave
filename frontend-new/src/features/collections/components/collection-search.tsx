import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import {
  IconAlertTriangleFilled,
  IconArrowRight,
  IconCheck,
  IconCircleCheckFilled,
  IconCopy,
  IconPlayerStopFilled,
} from '@tabler/icons-react';
import * as z from 'zod';
import { useClassicCollectionSearchMutation } from '../api';
import type { SearchResult } from '@/shared/api';
import { getApiErrorMessage } from '@/shared/api';
import { useCopyToClipboard } from '@/shared/hooks/use-copy-to-clipboard';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { Card, CardContent } from '@/shared/ui/card';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from '@/shared/ui/input-group';
import { Spinner } from '@/shared/ui/spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui/tabs';

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
  const results = classicSearchMutation.data?.results ?? [];
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

        <CollectionSearchStateCard
          isPending={isPending}
          isSuccess={isSuccess}
          results={results}
          submitError={submitError}
        />
      </div>
    </div>
  );
}

function CollectionSearchStateCard({
  isPending,
  isSuccess,
  results,
  submitError,
}: {
  isPending: boolean;
  isSuccess: boolean;
  results: Array<SearchResult>;
  submitError?: string;
}) {
  if (submitError) {
    return <CollectionSearchErrorState message={submitError} />;
  }

  if (isPending) {
    return <CollectionSearchLoadingState />;
  }

  if (!isSuccess) {
    return null;
  }

  if (results.length === 0) {
    return <CollectionSearchEmptyState />;
  }

  return <CollectionSearchResultsState results={results} />;
}

function CollectionSearchResultsState({
  results,
}: {
  results: Array<SearchResult>;
}) {
  const { copied, copy } = useCopyToClipboard();
  const resultsSummary = `Retrieved ${formatResultCount(results.length)}`;
  const resultTabContent = (
    <CollectionSearchTabContent
      copied={copied}
      copyLabel="Copy result content"
      label="Results ready"
      message="Placeholder content for classic search results. We will implement the exact Raw and Entities tab content next."
      onCopy={() =>
        void copy(
          `Classic search returned ${formatResultCount(results.length)}. Placeholder result content until exact tab content is implemented.`,
        )
      }
    />
  );

  return (
    <CollectionSearchStatusCard
      description={resultsSummary}
      icon={<IconCircleCheckFilled className="size-4 text-foreground/80" />}
      title="Answer ready"
    >
      <Tabs defaultValue="raw" className="gap-4">
        <TabsList
          variant="line"
          className="h-8 w-full justify-start gap-1 rounded-none border-b border-border p-0"
        >
          <TabsTrigger value="raw" className="flex-none p-1.5 text-sm">
            Raw
          </TabsTrigger>
          <TabsTrigger value="entities" className="flex-none p-1.5 text-sm">
            Entities
          </TabsTrigger>
        </TabsList>

        <TabsContent value="raw" className="space-y-1.5">
          {resultTabContent}
        </TabsContent>

        <TabsContent value="entities" className="space-y-1.5">
          {resultTabContent}
        </TabsContent>
      </Tabs>
    </CollectionSearchStatusCard>
  );
}

function CollectionSearchLoadingState() {
  return (
    <CollectionSearchStatusCard
      description="Collecting relevant results across connected sources."
      icon={<Spinner className="size-4 text-accent-foreground" />}
      title="Searching your data..."
    />
  );
}

function CollectionSearchErrorState({ message }: { message: string }) {
  const { copied, copy } = useCopyToClipboard();
  const errorTabContent = (
    <CollectionSearchTabContent
      copied={copied}
      copyLabel="Copy raw error"
      label="Search failed"
      message={message}
      messageClassName="text-destructive"
      onCopy={() => void copy(message)}
    />
  );

  return (
    <CollectionSearchStatusCard
      description="We couldn't complete this query. Try again or check Events."
      icon={<IconAlertTriangleFilled className="size-4 text-destructive" />}
      title="Search failed"
    >
      <Tabs defaultValue="raw" className="gap-4">
        <TabsList
          variant="line"
          className="h-8 w-full justify-start gap-1 rounded-none border-b border-border p-0"
        >
          <TabsTrigger value="raw" className="flex-none p-1.5 text-sm">
            Raw
          </TabsTrigger>
          <TabsTrigger value="entities" className="flex-none p-1.5 text-sm">
            Entities
          </TabsTrigger>
        </TabsList>

        <TabsContent value="raw" className="space-y-1.5">
          {errorTabContent}
        </TabsContent>

        <TabsContent value="entities" className="space-y-1.5">
          {errorTabContent}
        </TabsContent>
      </Tabs>
    </CollectionSearchStatusCard>
  );
}

function CollectionSearchEmptyState() {
  const { copied, copy } = useCopyToClipboard();
  const emptyMessage =
    "We couldn't find relevant results for this query across your connected sources. Try broader wording, a shorter query, or filter to a specific source.";
  const emptyTabContent = (
    <CollectionSearchTabContent
      copied={copied}
      copyLabel="Copy empty result message"
      label="No matches found"
      message={emptyMessage}
      onCopy={() => void copy(emptyMessage)}
    />
  );

  return (
    <CollectionSearchStatusCard
      description="We searched across connected sources but couldn't find results for this query."
      icon={<IconCircleCheckFilled className="size-4 text-foreground/80" />}
      title="No matches found"
    >
      <Tabs defaultValue="raw" className="gap-4">
        <TabsList
          variant="line"
          className="h-8 w-full justify-start gap-1 rounded-none border-b border-border p-0"
        >
          <TabsTrigger value="raw" className="flex-none p-1.5 text-sm">
            Raw
          </TabsTrigger>
          <TabsTrigger value="entities" className="flex-none p-1.5 text-sm">
            Entities
          </TabsTrigger>
        </TabsList>

        <TabsContent value="raw" className="space-y-1.5">
          {emptyTabContent}
        </TabsContent>

        <TabsContent value="entities" className="space-y-1.5">
          {emptyTabContent}
        </TabsContent>
      </Tabs>
    </CollectionSearchStatusCard>
  );
}

function CollectionSearchTabContent({
  copied,
  copyLabel,
  label,
  message,
  messageClassName,
  onCopy,
}: {
  copied: boolean;
  copyLabel: string;
  label: string;
  message: string;
  messageClassName?: string;
  onCopy: () => void;
}) {
  return (
    <>
      <p
        className={cn(
          'font-mono text-xs text-muted-foreground uppercase',
          messageClassName,
        )}
      >
        {label}
      </p>

      <div className="flex items-start justify-between gap-3">
        <p
          className={cn('text-sm leading-5 text-foreground', messageClassName)}
        >
          {message}
        </p>

        <Button
          aria-label={copyLabel}
          className="size-7 shrink-0 text-muted-foreground hover:text-foreground"
          onClick={onCopy}
          size="icon-xs"
          type="button"
          variant="ghost"
        >
          {copied ? (
            <IconCheck className="size-3.5" />
          ) : (
            <IconCopy className="size-3.5" />
          )}
        </Button>
      </div>
    </>
  );
}

function CollectionSearchStatusCard({
  children,
  description,
  icon,
  title,
}: {
  children?: React.ReactNode;
  description: React.ReactNode;
  icon: React.ReactNode;
  title: React.ReactNode;
}) {
  return (
    <Card size="sm" className="rounded-sm bg-foreground/5 shadow-none ring-0">
      <CardContent className="space-y-4 px-4 group-data-[size=sm]/card:px-4">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              'flex size-8 shrink-0 items-center justify-center rounded-sm border border-border bg-muted',
            )}
          >
            {icon}
          </div>

          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">{title}</p>
            <p className="font-mono text-xs text-muted-foreground">
              {description}
            </p>
          </div>
        </div>

        {children}
      </CardContent>
    </Card>
  );
}

function formatResultCount(count: number) {
  return `${count} result${count === 1 ? '' : 's'}`;
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
