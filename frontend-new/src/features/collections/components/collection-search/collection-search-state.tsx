import * as React from 'react';
import {
  IconAlertTriangleFilled,
  IconCheck,
  IconChevronDown,
  IconChevronRight,
  IconCircleCheckFilled,
  IconCopy,
} from '@tabler/icons-react';
import {
  formatCollectionSearchReasoningEvent,
  getCollectionSearchReasoningSummarySections,
} from './collection-search-reasoning-model';
import { CollectionSearchRawTabContent } from './collection-search-raw-tab';
import { CollectionSearchStatusCard } from './collection-search-status-card';
import type {
  CollectionSearchReasoningEvent,
  CollectionSearchTierState,
} from './use-collection-search-tiers';
import type { CollectionSearchReasoningSection } from './collection-search-reasoning-model';
import type { CollectionSearchTierName } from '../../lib/collection-search-model';
import { formatNumber } from '@/shared/format/format-number';
import { pluralize } from '@/shared/format/pluralize';
import { useCopyToClipboard } from '@/shared/hooks/use-copy-to-clipboard';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/shared/ui/collapsible';
import { Separator } from '@/shared/ui/separator';
import { Skeleton } from '@/shared/ui/skeleton';
import { Spinner } from '@/shared/ui/spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui/tabs';

const unavailableReasoningMessage =
  'No reasoning trace was captured for this search.';

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
      className="max-h-128 min-h-0 gap-4 overflow-hidden"
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
        <TabsContent value="reasoning" className="min-h-0 overflow-y-auto">
          <CollectionSearchReasoningTab state={state} />
        </TabsContent>
      ) : null}

      <TabsContent value="entities" className="min-h-0 overflow-y-auto pr-1">
        <CollectionSearchEntitiesTab state={state} />
      </TabsContent>

      <TabsContent value="raw" className="min-h-0 overflow-hidden">
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
  if (state.status === 'error') {
    return <CollectionSearchErrorTabContent message={state.error} />;
  }

  return (
    <CollectionSearchReasoningTabContent
      emptyCopyLabel="Copy reasoning placeholder message"
      emptyLabel="Reasoning unavailable"
      emptyMessage={unavailableReasoningMessage}
      events={state.reasoningEvents}
      finalEvent={state.status === 'success' ? state.rawFinalEvent : undefined}
      isFinished={state.status === 'success'}
      isLoading={state.status === 'loading'}
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
    return <CollectionSearchErrorTabContent message={state.error} />;
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
    return <CollectionSearchErrorTabContent message={state.error} />;
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
  finalEvent,
  isFinished = false,
  isLoading = false,
}: {
  emptyCopyLabel?: string;
  emptyLabel?: string;
  emptyMessage?: string;
  events?: Array<CollectionSearchReasoningEvent>;
  finalEvent?: CollectionSearchTierState['rawFinalEvent'];
  isFinished?: boolean;
  isLoading?: boolean;
}) {
  const reasoningEvents = events ?? [];

  if (reasoningEvents.length === 0 && !isLoading) {
    return (
      <CollectionSearchMessageTabContent
        copyLabel={emptyCopyLabel}
        label={emptyLabel}
        message={emptyMessage}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-4">
        {reasoningEvents.map((event, index) => {
          const formattedEvent = formatCollectionSearchReasoningEvent(event);

          if (!formattedEvent) {
            return null;
          }

          return (
            <div
              key={`${event.type}-${index}`}
              className="flex flex-col gap-2 sm:flex-row sm:justify-between sm:gap-6"
            >
              <div className="min-w-0 space-y-1 md:max-w-[440px]">
                <p
                  className={cn(
                    'font-mono text-xs text-muted-foreground',
                    formattedEvent.isInvalid ? 'line-through opacity-50' : '',
                  )}
                >
                  {formattedEvent.label}
                  {formattedEvent.labelSuffix ? (
                    <span className="ml-2">{formattedEvent.labelSuffix}</span>
                  ) : null}
                </p>

                {formattedEvent.detailLines?.length ? (
                  <div className="space-y-0.5">
                    {formattedEvent.detailLines.map(
                      (detailLine, detailIndex) => (
                        <p
                          key={`${detailLine}-${detailIndex}`}
                          className="text-xs leading-4 text-foreground"
                        >
                          {detailLine}
                        </p>
                      ),
                    )}
                  </div>
                ) : null}

                {formattedEvent.sections?.length ? (
                  <div className="space-y-0.5">
                    {formattedEvent.sections.map((section, sectionIndex) => (
                      <CollectionSearchReasoningSectionLine
                        key={`${section.label}-${section.collapsed}-${sectionIndex}`}
                        section={section}
                      />
                    ))}
                  </div>
                ) : null}
              </div>

              {formattedEvent.metaLabel ? (
                <span className="shrink-0 self-start font-mono text-xs text-muted-foreground sm:self-center">
                  {formattedEvent.metaLabel}
                </span>
              ) : null}
            </div>
          );
        })}

        {isLoading ? <CollectionSearchReasoningPendingLine /> : null}
      </div>

      {isFinished ? (
        <CollectionSearchReasoningSummary finalEvent={finalEvent} />
      ) : null}
    </div>
  );
}

function CollectionSearchErrorTabContent({ message }: { message?: string }) {
  return (
    <CollectionSearchMessageTabContent
      copyLabel="Copy error message"
      label="Search failed"
      message={message ?? 'Search failed. Try again.'}
      messageClassName="text-destructive"
    />
  );
}

function CollectionSearchReasoningPendingLine() {
  return (
    <div className="animate-pulse font-mono text-xs text-muted-foreground">
      Thinking...
    </div>
  );
}

function CollectionSearchReasoningSummary({
  finalEvent,
}: {
  finalEvent?: CollectionSearchTierState['rawFinalEvent'];
}) {
  const sections = getCollectionSearchReasoningSummarySections(finalEvent);

  if (!sections.length) {
    return null;
  }

  return (
    <>
      <Separator />

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-xs text-muted-foreground">
        {sections.map((section, index) => (
          <React.Fragment key={section}>
            {index > 0 ? (
              <Separator
                aria-hidden="true"
                orientation="vertical"
                className="hidden h-5 sm:block"
              />
            ) : null}

            <span>{section}</span>
          </React.Fragment>
        ))}
      </div>
    </>
  );
}

function CollectionSearchReasoningSectionLine({
  section,
}: {
  section: CollectionSearchReasoningSection;
}) {
  const [open, setOpen] = React.useState(false);

  if (!section.collapsed) {
    return null;
  }

  const label = `${section.label}: `;

  if (section.expandedLines.length === 0) {
    return (
      <p className="ml-0.5 text-xs leading-4 text-muted-foreground">
        <span className="opacity-50">{label}</span>
        {section.collapsed}
      </p>
    );
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-0.5 text-xs leading-4 text-muted-foreground hover:underline"
        >
          {open ? (
            <IconChevronDown className="size-3" />
          ) : (
            <IconChevronRight className="size-3" />
          )}

          <span className="opacity-50">{label}</span>
          <span>{section.collapsed}</span>
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent className="ml-4 space-y-px">
        {section.expandedLines.map((expandedLine, index) => (
          <p
            key={`${expandedLine}-${index}`}
            className="text-xs leading-4 text-muted-foreground"
          >
            {expandedLine}
          </p>
        ))}
      </CollapsibleContent>
    </Collapsible>
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

function formatResultCount(count: number) {
  return `${formatNumber(count)} ${pluralize(count, 'result')}`;
}
