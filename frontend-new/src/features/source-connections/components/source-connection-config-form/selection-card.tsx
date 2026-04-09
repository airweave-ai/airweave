import * as React from 'react';
import { cn } from '@/shared/tailwind/cn';
import { Label } from '@/shared/ui/label';

interface SelectionCardProps {
  selected: boolean;
  htmlFor: string;
  header: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  headerClassName?: string;
  contentClassName?: string;
}

export function SelectionCard({
  selected,
  htmlFor,
  header,
  children,
  className,
  headerClassName,
  contentClassName,
}: SelectionCardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border transition-colors',
        selected ? 'border-primary/20 bg-primary/10' : 'border-border',
        className,
      )}
    >
      <Label
        className={cn('flex cursor-pointer gap-3 p-4', headerClassName)}
        htmlFor={htmlFor}
      >
        {header}
      </Label>

      {selected && children ? (
        <div className={cn('space-y-4 px-4 pb-4', contentClassName)}>
          {children}
        </div>
      ) : null}
    </div>
  );
}
