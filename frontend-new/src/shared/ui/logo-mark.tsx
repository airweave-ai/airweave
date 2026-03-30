import type { ComponentProps } from 'react';
import { cn } from '@/shared/tailwind/cn';

export function LogoMark({ className, ...props }: ComponentProps<'span'>) {
  return (
    <span
      className={cn(
        'relative flex size-5 shrink-0 items-center justify-center overflow-hidden rounded-xs bg-foreground',
        className,
      )}
      {...props}
    >
      <span className="grid grid-cols-2 gap-px">
        <span className="size-1 rounded-[1px] bg-background/80" />
        <span className="size-1 rounded-[1px] bg-background/80" />
        <span className="size-1 rounded-[1px] bg-background/80" />
        <span className="size-1 rounded-[1px] bg-background/40" />
      </span>
    </span>
  );
}
