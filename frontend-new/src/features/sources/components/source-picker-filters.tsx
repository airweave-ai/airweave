import { Search } from 'lucide-react';
import type { SourceLabelCount } from '../utils';
import { cn } from '@/shared/tailwind/cn';
import { Badge } from '@/shared/ui/badge';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/shared/ui/input-group';

interface SourcePickerFiltersProps {
  activeLabel?: string;
  filteredSourceCount: number;
  isLoading: boolean;
  labelCounts: Array<SourceLabelCount>;
  onActiveLabelChange: (label?: string) => void;
  onSearchChange: (value: string) => void;
  search: string;
  totalSourceCount: number;
}

export function SourcePickerFilters({
  activeLabel,
  filteredSourceCount,
  isLoading,
  labelCounts,
  onActiveLabelChange,
  onSearchChange,
  search,
  totalSourceCount,
}: SourcePickerFiltersProps) {
  return (
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
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search..."
            className="text-foreground placeholder:text-muted-foreground"
          />
          <InputGroupAddon
            align="inline-end"
            className="text-sm font-medium text-muted-foreground"
          >
            {isLoading
              ? 'Loading...'
              : `${filteredSourceCount} result${filteredSourceCount === 1 ? '' : 's'}`}
          </InputGroupAddon>
        </InputGroup>

        <p className="font-mono text-sm text-muted-foreground">
          {totalSourceCount} Source{totalSourceCount === 1 ? '' : 's'} Available
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
                  onActiveLabelChange(isActive ? undefined : label)
                }
              >
                {label}{' '}
                <span className={cn(!isActive && 'text-muted-foreground')}>
                  [{count}]
                </span>
              </button>
            </Badge>
          );
        })}
      </div>
    </div>
  );
}
