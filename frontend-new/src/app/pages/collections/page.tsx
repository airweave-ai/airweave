import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { CollectionsTable } from '@/features/collections';
import { useListCollectionsQueryOptions } from '@/features/collections/api';
import type { Collection } from '@/shared/api';
import { cn } from '@/shared/tailwind/cn';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/shared/ui/input-group';
import { Spinner } from '@/shared/ui/spinner';

interface CollectionsPageProps {
  initialCollections: Array<Collection>;
  search?: string;
  onSearchChange: (search: string | undefined) => void;
}

export function CollectionsPage({
  initialCollections,
  search,
  onSearchChange,
}: CollectionsPageProps) {
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
    initialData: initialCollections,
  });

  const activeSearch = search ?? '';
  const displayedCollections = collections ?? initialCollections;
  const emptyMessage = error
    ? 'Failed to load collections.'
    : activeSearch
      ? `No collections found matching "${activeSearch}".`
      : 'No collections found.';

  return (
    <section className="space-y-4 px-13 py-1">
      <div className="space-y-1">
        <h1 className="font-heading text-lg font-semibold text-foreground">
          Collections
        </h1>
        <p className="text-sm text-muted-foreground">
          Browse your collections and basic metadata.
        </p>
      </div>

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
    </section>
  );
}
