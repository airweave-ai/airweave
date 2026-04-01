import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Plus, Search } from 'lucide-react';
import {
  CollectionFilterButtonGroup,
  CollectionsTable,
} from '@/features/collections';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/shared/ui/input-group';
import { Spinner } from '@/shared/ui/spinner';
import {
  CollectionCountBadge,
  useListCollectionsQueryOptions,
  normalizeSearch,
} from '@/features/collections';
import type { CollectionsSearch } from './search';

type CollectionsPageProps = CollectionsSearch & {
  onSearchChange: (search: string | undefined) => void;
};

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
  const normalizedSearch = normalizeSearch(search);
  const collectionsQueryOptions = useListCollectionsQueryOptions({
    search: normalizedSearch,
  });
  const {
    data: collections,
    error,
    isFetching,
  } = useQuery({
    ...collectionsQueryOptions,
    placeholderData: keepPreviousData,
  });

  const emptyMessage = error
    ? 'Failed to load collections.'
    : normalizedSearch
      ? `No collections found matching "${normalizedSearch}".`
      : 'No collections found.';

  return (
    <section className="space-y-5 px-13 py-1">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-1">
          <h1 className="font-heading text-lg font-semibold text-foreground">
            Collections
          </h1>
          <CollectionCountBadge />
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
            value={search}
            onChange={(e) => onSearchChange(e.target.value || undefined)}
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
          collections={collections ?? []}
          emptyMessage={emptyMessage}
        />
      </div>
    </section>
  );
}
