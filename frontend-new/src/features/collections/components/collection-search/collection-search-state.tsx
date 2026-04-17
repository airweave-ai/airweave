import * as React from 'react';
import {
  IconAlertTriangleFilled,
  IconCheck,
  IconCircleCheckFilled,
  IconCopy,
} from '@tabler/icons-react';
import { CollectionSearchRawTabContent } from './collection-search-raw-tab';
import { CollectionSearchStatusCard } from './collection-search-status-card';
import type {
  CollectionSearchReasoningEvent,
  CollectionSearchTierName,
  CollectionSearchTierState,
} from './use-collection-search-tiers';
import { formatNumber } from '@/shared/format/format-number';
import { pluralize } from '@/shared/format/pluralize';
import { useCopyToClipboard } from '@/shared/hooks/use-copy-to-clipboard';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { Skeleton } from '@/shared/ui/skeleton';
import { Spinner } from '@/shared/ui/spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui/tabs';

const unavailableReasoningMessage =
  'No reasoning trace was captured for this search.';

const failedReasoningMessage =
  'No reasoning trace was captured before the search failed.';

export type CollectionSearchTabValue = 'entities' | 'raw' | 'reasoning';

export function CollectionSearchState({
  onSelectedTabChange,
  selectedTab,
  tierName,
  state,
}: {
  onSelectedTabChange: (tab: CollectionSearchTabValue) => void;
  selectedTab?: CollectionSearchTabValue;
  tierName: CollectionSearchTierName;
  state: CollectionSearchTierState;
}) {
  if (state.status === 'idle') {
    return null;
  }

  const { description, icon, title } =
    getCollectionSearchStatusCardProps(state);

  return (
    <CollectionSearchStatusCard
      description={description}
      icon={icon}
      title={title}
    >
      <CollectionSearchTabs
        onSelectedTabChange={onSelectedTabChange}
        selectedTab={selectedTab}
        state={state}
        tierName={tierName}
      />
    </CollectionSearchStatusCard>
  );
}

function CollectionSearchTabs({
  onSelectedTabChange,
  selectedTab: storedSelectedTab,
  state,
  tierName,
}: {
  onSelectedTabChange: (tab: CollectionSearchTabValue) => void;
  selectedTab?: CollectionSearchTabValue;
  state: CollectionSearchTierState;
  tierName: CollectionSearchTierName;
}) {
  const hasReasoningTab = tierName === 'agentic';
  const selectedTab = resolveCollectionSearchSelectedTab({
    status: state.status,
    hasReasoningTab,
    selectedTab: storedSelectedTab,
  });

  if (state.status === 'loading' && !hasReasoningTab) {
    return null;
  }

  return (
    <Tabs
      className="gap-4"
      value={selectedTab}
      onValueChange={(value) =>
        onSelectedTabChange(value as CollectionSearchTabValue)
      }
    >
      <TabsList
        variant="line"
        className="h-8 w-full justify-start gap-1 rounded-none border-b border-border p-0"
      >
        {hasReasoningTab ? (
          <TabsTrigger value="reasoning" className="flex-none p-1.5 text-sm">
            Reasoning
          </TabsTrigger>
        ) : null}

        <TabsTrigger value="entities" className="flex-none p-1.5 text-sm">
          Entities
        </TabsTrigger>

        <TabsTrigger value="raw" className="flex-none p-1.5 text-sm">
          Raw
        </TabsTrigger>
      </TabsList>

      {hasReasoningTab ? (
        <TabsContent value="reasoning" className="space-y-1.5">
          <CollectionSearchReasoningTab state={state} />
        </TabsContent>
      ) : null}

      <TabsContent value="entities" className="space-y-1.5">
        <CollectionSearchEntitiesTab state={state} />
      </TabsContent>

      <TabsContent value="raw" className="space-y-1.5">
        <CollectionSearchRawTab state={state} />
      </TabsContent>
    </Tabs>
  );
}

function CollectionSearchReasoningTab({
  state,
}: {
  state: CollectionSearchTierState;
}) {
  return (
    <CollectionSearchReasoningTabContent
      emptyCopyLabel="Copy reasoning placeholder message"
      emptyLabel="Reasoning unavailable"
      emptyMessage={
        state.status === 'error'
          ? failedReasoningMessage
          : unavailableReasoningMessage
      }
      events={state.reasoningEvents}
    />
  );
}

function CollectionSearchEntitiesTab({
  state,
}: {
  state: CollectionSearchTierState;
}) {
  if (state.status === 'loading') {
    return <CollectionSearchEntitiesTabSkeleton />;
  }

  if (state.status === 'error') {
    return (
      <CollectionSearchMessageTabContent
        copyLabel="Copy error message"
        label="Search failed"
        message={state.error ?? 'Search failed. Try again.'}
        messageClassName="text-destructive"
      />
    );
  }

  if (isCollectionSearchEmpty(state)) {
    return (
      <CollectionSearchMessageTabContent
        copyLabel="Copy empty result message"
        label="No matches found"
        message="We couldn't find relevant results for this query across your connected sources. Try broader wording, a shorter query, or filter to a specific source."
      />
    );
  }

  return (
    <CollectionSearchMessageTabContent
      copyLabel="Copy placeholder message"
      label="Coming soon"
      message="Entities view is still a placeholder for search results."
    />
  );
}

function CollectionSearchRawTab({
  state,
}: {
  state: CollectionSearchTierState;
}) {
  if (state.status === 'loading') {
    return <CollectionSearchRawTabSkeleton />;
  }

  if (state.status === 'error') {
    return (
      <CollectionSearchRawTabContent
        payload={{ error: state.error ?? 'Search failed. Try again.' }}
      />
    );
  }

  const rawPayload = state.rawFinalEvent ?? state.data;

  if (rawPayload !== undefined) {
    return <CollectionSearchRawTabContent payload={rawPayload} />;
  }

  return (
    <CollectionSearchMessageTabContent
      copyLabel="Copy raw placeholder message"
      label="Raw response unavailable"
      message="Raw response is not available for this search."
    />
  );
}

function CollectionSearchReasoningTabContent({
  emptyCopyLabel = 'Copy reasoning placeholder message',
  emptyLabel = 'Reasoning unavailable',
  emptyMessage = unavailableReasoningMessage,
  events,
}: {
  emptyCopyLabel?: string;
  emptyLabel?: string;
  emptyMessage?: string;
  events?: Array<CollectionSearchReasoningEvent>;
}) {
  const { copied, copy } = useCopyToClipboard();
  const transcript = React.useMemo(
    () => (events ?? []).map(formatReasoningEventForClipboard).join('\n\n'),
    [events],
  );

  if (!events?.length) {
    return (
      <CollectionSearchMessageTabContent
        copyLabel={emptyCopyLabel}
        label={emptyLabel}
        message={emptyMessage}
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-xs text-muted-foreground uppercase">
          Reasoning trace
        </p>

        <Button
          aria-label="Copy reasoning trace"
          className="size-7 shrink-0 text-muted-foreground hover:text-foreground"
          onClick={() => void copy(transcript)}
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

      <div className="space-y-2">
        {events.map((event, index) => {
          const formattedEvent = formatReasoningEvent(event);

          return (
            <div
              key={`${event.type}-${index}`}
              className="space-y-2 rounded-sm border border-border bg-background/60 p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="font-mono text-xs text-muted-foreground uppercase">
                  {formattedEvent.label}
                </p>

                {formattedEvent.durationLabel ? (
                  <span className="font-mono text-[11px] text-muted-foreground">
                    {formattedEvent.durationLabel}
                  </span>
                ) : null}
              </div>

              <p className="text-sm leading-5 text-foreground">
                {formattedEvent.message}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CollectionSearchMessageTabContent({
  copyLabel,
  label,
  message,
  messageClassName,
}: {
  copyLabel: string;
  label: string;
  message: string;
  messageClassName?: string;
}) {
  const { copied, copy } = useCopyToClipboard();

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
          onClick={() => void copy(message)}
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

function CollectionSearchEntitiesTabSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-3 w-24 bg-muted/50" />

      {Array.from({ length: 3 }).map((_, index) => (
        <div
          key={index}
          className="space-y-3 rounded-sm border border-border bg-background/60 p-3"
        >
          <div className="flex items-center justify-between gap-3">
            <Skeleton className="h-4 w-36 bg-muted/60" />
            <Skeleton className="h-4 w-20 bg-muted/40" />
          </div>

          <div className="space-y-2">
            <Skeleton className="h-3 w-full bg-muted/50" />
            <Skeleton className="h-3 w-5/6 bg-muted/40" />
          </div>
        </div>
      ))}
    </div>
  );
}

function CollectionSearchRawTabSkeleton() {
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Skeleton className="size-7 rounded-sm bg-muted/50" />
      </div>

      <div className="space-y-2 rounded-sm border border-border bg-background/60 p-3">
        <Skeleton className="h-3 w-28 bg-muted/50" />
        <Skeleton className="h-3 w-full bg-muted/60" />
        <Skeleton className="h-3 w-11/12 bg-muted/50" />
        <Skeleton className="h-3 w-4/5 bg-muted/40" />
        <Skeleton className="h-3 w-10/12 bg-muted/50" />
        <Skeleton className="h-3 w-2/3 bg-muted/40" />
      </div>
    </div>
  );
}

function getCollectionSearchStatusCardProps(state: CollectionSearchTierState) {
  if (state.status === 'loading') {
    return {
      description: 'Collecting relevant results across connected sources.',
      icon: <Spinner className="size-4 text-accent-foreground" />,
      title: 'Searching your data...',
    };
  }

  if (state.status === 'error') {
    return {
      description:
        "We couldn't complete this query. Try again or check the error details.",
      icon: <IconAlertTriangleFilled className="size-4 text-destructive" />,
      title: 'Search failed',
    };
  }

  if (isCollectionSearchEmpty(state)) {
    return {
      description:
        "We searched across connected sources but couldn't find results for this query.",
      icon: <IconCircleCheckFilled className="size-4 text-foreground/80" />,
      title: 'No matches found',
    };
  }

  const resultsCount = state.data?.results?.length ?? 0;

  return {
    description: `Retrieved ${formatResultCount(resultsCount)}`,
    icon: <IconCircleCheckFilled className="size-4 text-foreground/80" />,
    title: 'Answer ready',
  };
}

function isCollectionSearchEmpty(state: CollectionSearchTierState) {
  return (
    state.status === 'success' &&
    ((state.data?.results?.length ?? 0) === 0 || !state.data)
  );
}

function resolveCollectionSearchSelectedTab({
  status,
  hasReasoningTab,
  selectedTab,
}: {
  status: CollectionSearchTierState['status'];
  hasReasoningTab: boolean;
  selectedTab?: CollectionSearchTabValue;
}) {
  if (selectedTab) {
    return selectedTab;
  }

  if (hasReasoningTab && status === 'loading') {
    return 'reasoning';
  }
  return 'entities';
}

function formatReasoningEvent(event: CollectionSearchReasoningEvent) {
  switch (event.type) {
    case 'thinking':
      return {
        durationLabel: formatDuration(event.duration_ms),
        label: 'Thinking',
        message:
          event.text ??
          event.thinking ??
          'Working through the query and planning the next step.',
      };

    case 'tool_call':
      return {
        durationLabel: formatDuration(event.duration_ms),
        label: 'Tool call',
        message: `Used ${event.tool_name}.`,
      };

    case 'reranking':
      return {
        durationLabel: formatDuration(event.duration_ms),
        label: 'Reranking',
        message: 'Reordered candidate results by relevance.',
      };
  }
}

function formatReasoningEventForClipboard(
  event: CollectionSearchReasoningEvent,
) {
  const formattedEvent = formatReasoningEvent(event);

  return [
    formattedEvent.label,
    formattedEvent.message,
    formattedEvent.durationLabel,
  ]
    .filter(Boolean)
    .join(' | ');
}

function formatDuration(durationMs: number) {
  return `${formatNumber(durationMs)}ms`;
}

function formatResultCount(count: number) {
  return `${formatNumber(count)} ${pluralize(count, 'result')}`;
}
