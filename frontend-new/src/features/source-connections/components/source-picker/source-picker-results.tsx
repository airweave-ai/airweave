import { SearchX } from 'lucide-react';

import { SourceCard } from '../source-card';
import type { Source } from '@/shared/api';
import { ErrorState } from '@/shared/components/error-state';
import { Button } from '@/shared/ui/button';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/shared/ui/empty';
import { Loader } from '@/shared/components/loader';

interface SourcePickerResultsProps {
  error: unknown;
  filteredSources: Array<Source>;
  isLoading: boolean;
  onClearFilters: () => void;
  onRetry: () => void;
  onSelectSource?: (source: Source) => void;
  search?: string;
}

export function SourcePickerResults({
  error,
  filteredSources,
  isLoading,
  onClearFilters,
  onRetry,
  onSelectSource,
  search,
}: SourcePickerResultsProps) {
  if (isLoading) {
    return <Loader />;
  }

  if (error) {
    return (
      <ErrorState
        description="An unexpected error occurred while loading sources."
        onRetry={onRetry}
        title="We couldn't load sources"
      />
    );
  }

  if (filteredSources.length === 0) {
    const hasSearch = Boolean(search?.trim());

    return (
      <Empty className="min-h-full">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <SearchX className="size-4" />
          </EmptyMedia>

          <EmptyTitle>
            {hasSearch
              ? `No sources found for "${search?.trim()}"`
              : 'No sources available.'}
          </EmptyTitle>
          <EmptyDescription>
            {hasSearch
              ? 'Try a different name, check spelling, or clear your search to see all available sources.'
              : 'There are no sources to display right now.'}
          </EmptyDescription>
        </EmptyHeader>

        {hasSearch ? (
          <EmptyContent>
            <Button type="button" variant="outline" onClick={onClearFilters}>
              Clear Search
            </Button>
          </EmptyContent>
        ) : null}
      </Empty>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-3">
      {filteredSources.map((source) => (
        <SourceCard
          key={source.short_name}
          source={source}
          onClick={() => onSelectSource?.(source)}
        />
      ))}
    </div>
  );
}
