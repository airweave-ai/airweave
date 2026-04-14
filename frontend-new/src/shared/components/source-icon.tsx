import type { ComponentProps } from 'react';
import type { AppIconVariant } from '@/shared/icons/get-app-icon-url';
import { getAppIconUrl } from '@/shared/icons/get-app-icon-url';
import { cn } from '@/shared/tailwind/cn';

interface SourceIconProps extends ComponentProps<'div'> {
  name: string;
  shortName?: string;
  variant?: AppIconVariant;
}

export function SourceIcon({
  className,
  name,
  shortName,
  variant = 'color',
  ...props
}: SourceIconProps) {
  const sourceIconSrc = shortName ? getAppIconUrl(shortName, variant) : null;

  return (
    <div
      className={cn(
        'flex size-5 shrink-0 items-center justify-center text-xs font-semibold',
        !sourceIconSrc && 'rounded-sm border',
        className,
      )}
      {...props}
    >
      {sourceIconSrc ? (
        <img
          alt=""
          aria-hidden="true"
          className="size-full object-contain"
          src={sourceIconSrc}
        />
      ) : (
        <span>{name.charAt(0).toUpperCase()}</span>
      )}
    </div>
  );
}
