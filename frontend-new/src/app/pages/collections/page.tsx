import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Plus, Search } from 'lucide-react';
import type { Collection } from '@/shared/api';
import {
  CollectionFilterButtonGroup,
  CollectionsTable,
} from '@/features/collections';
import {
  useCollectionCountQueryOptions,
  useListCollectionsQueryOptions,
} from '@/features/collections/api';
import { cn } from '@/shared/tailwind/cn';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/shared/ui/input-group';
import { Spinner } from '@/shared/ui/spinner';

interface CollectionsPageProps {
  search?: string;
  onSearchChange: (search: string | undefined) => void;
}

const collectionsPageFilters = [
  'Health',
  'Connections',
  'Status',
  'Last Sync',
] as const;

export function CollectionsPage({
  search,
  onSearchChange,
}: CollectionsPageProps) {
  const collectionCountQueryOptions = useCollectionCountQueryOptions();
  const { data: collectionCount, isPending: isCollectionCountPending } =
    useQuery(collectionCountQueryOptions);
  const collectionsQueryOptions = useListCollectionsQueryOptions({
    search,
  });
  const {
    data: collections,
    error,
    isFetching,
  } = useQuery({
    ...collectionsQueryOptions,
    placeholderData: keepPreviousData,
  });

  const activeSearch = search ?? '';
  const displayedCollections = collections;
  const displayedCollectionCount = isCollectionCountPending
    ? '...'
    : collectionCount;
  const emptyMessage = error
    ? 'Failed to load collections.'
    : activeSearch
      ? `No collections found matching "${activeSearch}".`
      : 'No collections found.';

  return (
    <section className="space-y-5 px-13 py-1">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-1">
          <h1 className="font-heading text-lg font-semibold text-foreground">
            Collections
          </h1>
          <Badge
            variant="secondary"
            className="text-[0.625rem] text-muted-foreground"
          >
            {displayedCollectionCount}
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {collectionsPageFilters.map((filter) => (
            <CollectionFilterButtonGroup key={filter} label={filter} />
          ))}

          <Button data-icon="inline-start" type="button">
            <Plus />
            Create Collection
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <InputGroup className="w-full">
          <InputGroupAddon align="inline-start">
            <Search className="size-4" />
          </InputGroupAddon>
          <InputGroupInput
            value={activeSearch}
            onChange={(e) => onSearchChange(e.target.value.trim() || undefined)}
            placeholder="Search collections by name or ID..."
          />
          <InputGroupAddon
            align="inline-end"
            aria-hidden={!isFetching}
            className="w-8 justify-center"
          >
            <Spinner
              className={cn(
                'size-4 transition-opacity duration-150',
                isFetching ? 'opacity-100 delay-150' : 'opacity-0 delay-0',
              )}
            />
            <span className="sr-only">Loading collections</span>
          </InputGroupAddon>
        </InputGroup>

        <CollectionsTable
          collections={displayedCollections}
          emptyMessage={emptyMessage}
        />
      </div>
    </section>
  );
}
