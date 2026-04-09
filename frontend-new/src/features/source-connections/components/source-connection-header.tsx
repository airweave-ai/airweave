import * as React from 'react';
import { IconArrowUpRight } from '@tabler/icons-react';
import { getSourceDocsUrl } from '../lib/source-docs-url';
import { SourceIcon } from './source-icon';
import type { Source } from '@/shared/api';
import { cn } from '@/shared/tailwind/cn';

export interface SourceConnectionHeaderProps {
  aside?: React.ReactNode;
  className?: string;
  source: Pick<Source, 'name' | 'short_name'>;
}

export function SourceConnectionHeader({
  aside,
  className,
  source,
}: SourceConnectionHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xs border border-border bg-muted">
          <SourceIcon
            className="size-4"
            name={source.name}
            shortName={source.short_name}
          />
        </div>

        <div className="min-w-0 space-y-0.5">
          <h2 className="text-base font-medium text-foreground">
            Connect {source.name}
          </h2>

          <a
            href={getSourceDocsUrl(source.short_name)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-mono text-sm text-muted-foreground capitalize transition-colors hover:text-foreground"
          >
            See docs
            <IconArrowUpRight className="size-4" />
          </a>
        </div>
      </div>

      {aside ? <div className="shrink-0">{aside}</div> : null}
    </div>
  );
}
