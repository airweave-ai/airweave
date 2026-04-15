import * as React from 'react';
import {
  IconAlertTriangleFilled,
  IconCheck,
  IconCircleCheckFilled,
  IconCopy,
} from '@tabler/icons-react';
import { CollectionSearchRawTabContent } from './collection-search-raw-tab';
import { CollectionSearchStatusCard } from './collection-search-status-card';
import type { SearchV2Response } from '@/shared/api';
import { useCopyToClipboard } from '@/shared/hooks/use-copy-to-clipboard';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { Spinner } from '@/shared/ui/spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui/tabs';

const entitiesPlaceholderMessage =
  'Entities view is still a placeholder for classic search results.';

const emptyResultsMessage =
  "We couldn't find relevant results for this query across your connected sources. Try broader wording, a shorter query, or filter to a specific source.";

export function CollectionSearchState({
  isPending,
  isSuccess,
  response,
  resultsCount,
  submitError,
}: {
  isPending: boolean;
  isSuccess: boolean;
  response?: SearchV2Response;
  resultsCount: number;
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

  if (resultsCount === 0 || !response) {
    return <CollectionSearchEmptyState />;
  }

  return <CollectionSearchResultsState response={response} />;
}

function CollectionSearchResultsState({
  response,
}: {
  response: SearchV2Response;
}) {
  const { copied, copy } = useCopyToClipboard();
  const results = response.results ?? [];
  const resultsSummary = `Retrieved ${formatResultCount(results.length)}`;
  const entitiesTabContent = (
    <CollectionSearchMessageTabContent
      copied={copied}
      copyLabel="Copy placeholder message"
      label="Coming soon"
      message={entitiesPlaceholderMessage}
      onCopy={() => void copy(entitiesPlaceholderMessage)}
    />
  );

  return (
    <CollectionSearchStatusCard
      description={resultsSummary}
      icon={<IconCircleCheckFilled className="size-4 text-foreground/80" />}
      title="Answer ready"
    >
      <CollectionSearchTabs
        rawContent={<CollectionSearchRawTabContent response={response} />}
        entitiesContent={entitiesTabContent}
      />
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
    <CollectionSearchMessageTabContent
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
      <CollectionSearchTabs
        rawContent={errorTabContent}
        entitiesContent={errorTabContent}
      />
    </CollectionSearchStatusCard>
  );
}

function CollectionSearchEmptyState() {
  const { copied, copy } = useCopyToClipboard();
  const emptyTabContent = (
    <CollectionSearchMessageTabContent
      copied={copied}
      copyLabel="Copy empty result message"
      label="No matches found"
      message={emptyResultsMessage}
      onCopy={() => void copy(emptyResultsMessage)}
    />
  );

  return (
    <CollectionSearchStatusCard
      description="We searched across connected sources but couldn't find results for this query."
      icon={<IconCircleCheckFilled className="size-4 text-foreground/80" />}
      title="No matches found"
    >
      <CollectionSearchTabs
        rawContent={emptyTabContent}
        entitiesContent={emptyTabContent}
      />
    </CollectionSearchStatusCard>
  );
}

function CollectionSearchTabs({
  rawContent,
  entitiesContent,
}: {
  rawContent: React.ReactNode;
  entitiesContent: React.ReactNode;
}) {
  return (
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
        {rawContent}
      </TabsContent>

      <TabsContent value="entities" className="space-y-1.5">
        {entitiesContent}
      </TabsContent>
    </Tabs>
  );
}

function CollectionSearchMessageTabContent({
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

function formatResultCount(count: number) {
  return `${count} result${count === 1 ? '' : 's'}`;
}
