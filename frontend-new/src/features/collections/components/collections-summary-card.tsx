import * as React from 'react';
import { useSuspenseQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { Maximize2, Search } from 'lucide-react';
import {
  useCollectionCountQueryOptions,
  useListCollectionsQueryOptions,
} from '../api';
import {
  demoCollectionDescription,
  useDemoCollection,
} from '../demo-collection';
import { CollectionActionsMenu } from './collection-actions-menu';
import {
  CollectionSourceConnections,
  CollectionSourceConnectionsSkeleton,
} from './collection-source-connections';
import { CollectionStatusBadge } from './collection-status-badge';
import { CollectionCountBadge } from './collection-count-badge';
import { CollectionsSearchEmptyState } from './collections-search-empty-state';
import type { Collection } from '@/shared/api';
import type { ReactNode } from 'react';
import { formatNumber } from '@/shared/format/format-number';
import { pluralize } from '@/shared/format/pluralize';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import { Card, CardContent, CardHeader } from '@/shared/ui/card';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/shared/ui/input-group';
import { Skeleton } from '@/shared/ui/skeleton';

export function CollectionsSummaryCard({
  createCollectionAction,
}: {
  createCollectionAction?: ReactNode;
}) {
  const [search, setSearch] = React.useState<string | undefined>(undefined);
  const deferredSearch = React.useDeferredValue(search);
  const normalizedSearch = (deferredSearch ?? '').trim();
  const hasActiveSearch = normalizedSearch.length > 0;
  const collectionCountQueryOptions = useCollectionCountQueryOptions({});
  const { data: collectionCount } = useSuspenseQuery(
    collectionCountQueryOptions,
  );

  const hasCollections = collectionCount > 0;

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <h2 className="font-heading text-base font-semibold text-foreground">
            Collections
          </h2>
          <CollectionCountBadge />
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <InputGroup className="w-full sm:w-64">
            <InputGroupAddon align="inline-start">
              <Search className="size-4" />
            </InputGroupAddon>
            <InputGroupInput
              value={search ?? ''}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search..."
            />
          </InputGroup>

          <div className="flex items-center gap-2">
            {createCollectionAction}
            <Button asChild size="icon-lg" type="button" variant="outline">
              <Link to="/collections">
                <Maximize2 />
                <span className="sr-only">Expand collections</span>
              </Link>
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {!hasCollections && !hasActiveSearch ? (
          <DemoCollectionContent />
        ) : (
          <React.Suspense fallback={<CollectionsSummaryCardContentSkeleton />}>
            <CollectionsSummaryCardListContent
              search={normalizedSearch}
              onClearSearch={() => setSearch(undefined)}
            />
          </React.Suspense>
        )}
      </CardContent>
    </Card>
  );
}

function CollectionsSummaryCardListContent({
  search,
  onClearSearch,
}: {
  search?: string;
  onClearSearch: () => void;
}) {
  const collectionsQueryOptions = useListCollectionsQueryOptions({ search });
  const { data: collections } = useSuspenseQuery({
    ...collectionsQueryOptions,
  });

  if (search && collections.length === 0) {
    return (
      <CollectionsSearchEmptyState
        search={search}
        onClearSearch={onClearSearch}
      />
    );
  }

  return (
    <ul className="space-y-1">
      {collections.map((collection) => (
        <CollectionListItem key={collection.id} collection={collection} />
      ))}
    </ul>
  );
}

function CollectionsSummaryCardContentSkeleton() {
  return (
    <ul className="space-y-1">
      {Array.from({ length: 3 }).map((_, index) => (
        <li
          key={index}
          className="flex flex-col gap-3 rounded-sm bg-foreground/5 px-3 py-2 md:flex-row md:items-center md:justify-between"
        >
          <div className="space-y-1">
            <Skeleton className="h-4 w-32 bg-muted/60" />
            <Skeleton className="h-3 w-24 bg-muted/40" />
          </div>

          <div className="flex items-center justify-between gap-4 md:justify-start">
            <CollectionSourceConnectionsSkeleton />

            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-18 rounded-full bg-muted/50" />
              <Skeleton className="size-8 rounded-sm bg-muted/50" />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function DemoCollectionContent() {
  const demoCollection = useDemoCollection();

  return (
    <ul>
      <CollectionListItem
        collection={demoCollection}
        header={
          <Badge
            variant="outline"
            className="border-none bg-foreground/5 text-muted-foreground uppercase"
          >
            Demo
          </Badge>
        }
        description={demoCollectionDescription}
      />
    </ul>
  );
}

function CollectionListItem({
  collection,
  header,
  description,
}: {
  collection: Collection;
  header?: ReactNode;
  description?: ReactNode;
}) {
  const sourceConnections = collection.source_connection_summaries ?? [];
  const sourceCount = sourceConnections.length;

  return (
    <li className="flex flex-col gap-3 rounded-sm bg-foreground/5 px-3 py-2 md:flex-row md:items-center md:justify-between">
      <div className="space-y-0.5">
        <div className="flex flex-wrap items-center gap-1">
          <Link
            to="/collections/$collectionId"
            params={{ collectionId: collection.readable_id }}
          >
            <p className="text-sm font-medium text-foreground">
              {collection.name}
            </p>
          </Link>
          {header}
        </div>

        <p className="font-mono text-xs leading-5 text-muted-foreground">
          {description ?? (
            <span className="flex items-center gap-1.5">
              {formatNumber(sourceCount)} {pluralize(sourceCount, 'Connection')}{' '}
              {/* TODO: replace with fetched number of entities */}
              <span className="size-[3px] rounded-full bg-current" /> 0{' '}
              {pluralize(0, 'Entity', 'Entities')}
            </span>
          )}
        </p>
      </div>

      <div className="flex items-center justify-between gap-4 md:justify-start">
        <CollectionSourceConnections sourceConnections={sourceConnections} />

        <div className="flex items-center gap-2">
          {collection.status ? (
            <CollectionStatusBadge status={collection.status} />
          ) : null}

          <CollectionActionsMenu collectionId={collection.id} />
        </div>
      </div>
    </li>
  );
}
