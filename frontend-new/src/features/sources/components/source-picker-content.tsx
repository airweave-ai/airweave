import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, X } from 'lucide-react';
import { useListSourcesQueryOptions } from '../api';
import { filterSources, getSourceLabelCounts } from '../utils';
import { SourceCard } from './source-card';
import type { Source } from '@/shared/api';
import { cn } from '@/shared/tailwind/cn';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/shared/ui/input-group';
import { Spinner } from '@/shared/ui/spinner';

interface SourcePickerContentProps {
  onClose: () => void;
  onSelectSource?: (source: Source) => void;
  selectedShortName?: string;
}

export function SourcePickerContent({
  onClose,
  onSelectSource,
  selectedShortName,
}: SourcePickerContentProps) {
  const [search, setSearch] = React.useState('');
  const [activeLabel, setActiveLabel] = React.useState<string | undefined>();
  const sourcesQueryOptions = useListSourcesQueryOptions();
  const {
    data: sources = [],
    error,
    isLoading,
    isFetching,
    refetch,
  } = useQuery(sourcesQueryOptions);

  const filteredSources = React.useMemo(
    () => filterSources({ activeLabel, search, sources }),
    [activeLabel, search, sources],
  );

  const labelCounts = React.useMemo(
    () => getSourceLabelCounts(sources),
    [sources],
  );
  const hasFilters = search.trim().length > 0 || Boolean(activeLabel);
  const filteredSourceCount = filteredSources.length;
  const totalSourceCount = sources.length;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center justify-between gap-6 border-b border-border px-6 py-4">
        <div className="min-w-0 space-y-1">
          <DialogTitle className="text-xl font-semibold text-foreground">
            Select Source
          </DialogTitle>
          <DialogDescription className="font-mono text-sm text-muted-foreground">
            Make your content searchable for your agent.
          </DialogDescription>
        </div>

        <Button
          type="button"
          variant="outline"
          size="icon"
          className="bg-foreground/5 text-foreground hover:bg-foreground/10"
          onClick={onClose}
        >
          <X className="size-4" />
          <span className="sr-only">Close source picker</span>
        </Button>
      </header>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden xl:flex-row">
        <aside className="flex w-full shrink-0 flex-col border-b border-border px-6 py-6 xl:w-110 xl:border-r xl:border-b-0">
          <div className="space-y-4">
            <div className="space-y-2.5">
              <InputGroup className="h-10 border-border bg-foreground/5 text-foreground">
                <InputGroupAddon
                  align="inline-start"
                  className="text-muted-foreground"
                >
                  <Search className="size-4" />
                </InputGroupAddon>
                <InputGroupInput
                  autoFocus
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search..."
                  className="text-foreground placeholder:text-muted-foreground"
                />
                <InputGroupAddon
                  align="inline-end"
                  className="text-sm font-medium text-muted-foreground"
                >
                  {isLoading || isFetching
                    ? 'Loading...'
                    : `${filteredSourceCount} result${filteredSourceCount === 1 ? '' : 's'}`}
                </InputGroupAddon>
              </InputGroup>

              <p className="font-mono text-sm text-muted-foreground">
                {totalSourceCount} Source{totalSourceCount === 1 ? '' : 's'}{' '}
                Available
              </p>
            </div>

            <div className="h-px w-full bg-border" />

            <div className="flex flex-wrap gap-2">
              {labelCounts.map(({ count, label }) => {
                const isActive = activeLabel === label;

                return (
                  <Badge
                    key={label}
                    asChild
                    variant="outline"
                    className={cn(
                      'bg-transparent font-mono text-xs text-foreground uppercase transition-colors hover:bg-foreground/5',
                      isActive &&
                        'bg-foreground text-background hover:bg-foreground/90',
                    )}
                  >
                    <button
                      type="button"
                      onClick={() =>
                        setActiveLabel(isActive ? undefined : label)
                      }
                    >
                      {label}{' '}
                      <span
                        className={cn(!isActive && 'text-muted-foreground')}
                      >
                        [{count}]
                      </span>
                    </button>
                  </Badge>
                );
              })}
            </div>
          </div>
        </aside>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
          {isLoading ? (
            <div className="flex min-h-48 items-center justify-center">
              <Spinner className="size-5 text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex min-h-48 flex-col items-center justify-center gap-3 text-center">
              <p className="text-sm text-muted-foreground">
                Failed to load sources.
              </p>
              <Button
                type="button"
                variant="outline"
                className="border-border bg-foreground/5 text-foreground hover:bg-foreground/10"
                onClick={() => void refetch()}
              >
                Retry
              </Button>
            </div>
          ) : filteredSources.length === 0 ? (
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
                  onClick={() => {
                    setSearch('');
                    setActiveLabel(undefined);
                  }}
                >
                  Clear filters
                </Button>
              ) : null}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
              {filteredSources.map((source) => (
                <SourceCard
                  key={source.short_name}
                  source={source}
                  selected={source.short_name === selectedShortName}
                  onClick={() => onSelectSource?.(source)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
