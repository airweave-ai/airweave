import * as React from 'react';
import { IconArrowUpRight } from '@tabler/icons-react';
import { getSourceDocsUrl } from '../lib/source-docs-url';
import type { Source } from '@/shared/api';
import { SourceIconTile } from '@/shared/components/source-icon-tile';
import { cn } from '@/shared/tailwind/cn';

export interface SourceConnectionHeaderProps {
  aside?: React.ReactNode;
  className?: string;
  source: Pick<Source, 'name' | 'short_name'>;
  title?: React.ReactNode;
}

export function SourceConnectionHeader({
  aside,
  className,
  source,
  title,
}: SourceConnectionHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between',
        className,
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <SourceIconTile name={source.name} shortName={source.short_name} />

        <div className="min-w-0 space-y-0.5">
          <h2 className="flex items-center gap-1 text-base font-medium text-foreground">
            {title ?? `Connect ${source.name}`}
          </h2>

          <a
            href={getSourceDocsUrl(source.short_name)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-0.5 font-mono text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            See Docs
            <IconArrowUpRight className="size-3.5" />
          </a>
        </div>
      </div>

      {aside ? <div className="shrink-0">{aside}</div> : null}
    </div>
  );
}
