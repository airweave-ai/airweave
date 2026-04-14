import type { Source } from '@/shared/api';
import { SourceIcon } from '@/shared/components/source-icon';
import { cn } from '@/shared/tailwind/cn';
import { Badge } from '@/shared/ui/badge';

interface SourceCardProps {
  onClick: () => void;
  selected?: boolean;
  source: Source;
}

export function SourceCard({
  onClick,
  selected = false,
  source,
}: SourceCardProps) {
  const primaryLabel = source.labels?.find((label) => label.trim().length > 0);

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex h-20 items-center justify-between rounded-md border border-border bg-foreground/5 p-4 text-left transition-colors hover:border-foreground/20 hover:bg-foreground/10',
        selected &&
          'border-foreground/30 bg-foreground/10 ring-1 ring-foreground/20',
      )}
    >
      <div className="flex min-w-0 items-center gap-1.5">
        <SourceIcon name={source.name} shortName={source.short_name} />
        <span className="truncate text-sm font-medium text-foreground">
          {source.name}
        </span>
      </div>

      {primaryLabel ? (
        <Badge
          variant="outline"
          className="border-border bg-transparent font-mono text-xs text-foreground uppercase"
        >
          {primaryLabel}
        </Badge>
      ) : null}
    </button>
  );
}
