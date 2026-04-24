import type { ComponentProps, ReactNode } from 'react';
import { cn } from '@/shared/tailwind/cn';

interface BrandIconProps extends ComponentProps<'div'> {
  src?: string | null;
  fallback: ReactNode;
}

export function BrandIcon({
  className,
  fallback,
  src,
  ...props
}: BrandIconProps) {
  return (
    <div
      className={cn(
        'flex size-5 shrink-0 items-center justify-center overflow-hidden text-xs font-semibold text-foreground',
        !src && 'rounded-sm border',
        className,
      )}
      {...props}
    >
      {src ? (
        <img
          alt=""
          aria-hidden="true"
          className="size-full object-contain"
          src={src}
        />
      ) : (
        fallback
      )}
    </div>
  );
}
