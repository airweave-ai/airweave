import * as React from 'react';
import { SourceIcon } from './source-icon';
import { cn } from '@/shared/tailwind/cn';

type SourceIconTileProps = React.ComponentProps<'div'> & {
  iconClassName?: string;
  name: string;
  shortName?: string;
};

export function SourceIconTile({
  className,
  iconClassName,
  name,
  shortName,
  ...props
}: SourceIconTileProps) {
  return (
    <div
      className={cn(
        'flex size-10 shrink-0 items-center justify-center rounded-xs border border-border bg-muted',
        className,
      )}
      {...props}
    >
      <SourceIcon
        className={cn('size-4', iconClassName)}
        name={name}
        shortName={shortName}
      />
    </div>
  );
}
