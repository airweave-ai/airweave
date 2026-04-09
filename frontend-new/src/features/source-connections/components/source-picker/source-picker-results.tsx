import { SourceCard } from '../source-card';
import type { Source } from '@/shared/api';
import { Button } from '@/shared/ui/button';
import { Spinner } from '@/shared/ui/spinner';

interface SourcePickerResultsProps {
  error: unknown;
  filteredSources: Array<Source>;
  hasFilters: boolean;
  isLoading: boolean;
  onClearFilters: () => void;
  onRetry: () => void;
  onSelectSource?: (source: Source) => void;
}

export function SourcePickerResults({
  error,
  filteredSources,
  hasFilters,
  isLoading,
  onClearFilters,
  onRetry,
  onSelectSource,
}: SourcePickerResultsProps) {
  if (isLoading) {
    return (
      <div className="flex min-h-48 items-center justify-center">
        <Spinner className="size-5 text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-48 flex-col items-center justify-center gap-3 text-center">
        <p className="text-sm text-muted-foreground">Failed to load sources.</p>
        <Button
          type="button"
          variant="outline"
          className="border-border bg-foreground/5 text-foreground hover:bg-foreground/10"
          onClick={onRetry}
        >
          Retry
        </Button>
      </div>
    );
  }

  if (filteredSources.length === 0) {
    return (
      <div className="flex min-h-48 flex-col items-center justify-center gap-3 text-center">
        <p className="text-sm text-muted-foreground">
          {hasFilters
            ? 'No sources match your filters.'
            : 'No sources available.'}
        </p>
        {hasFilters ? (
          <Button
            type="button"
            variant="ghost"
            className="text-foreground hover:bg-foreground/5"
            onClick={onClearFilters}
          >
            Clear filters
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
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
