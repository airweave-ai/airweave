import { BrandIcon } from './brand-icon';
import type { ComponentProps } from 'react';
import type { AppIconVariant } from '@/shared/icons/get-app-icon-url';
import { getAppIconUrl } from '@/shared/icons/get-app-icon-url';

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
    <BrandIcon
      className={className}
      fallback={<span>{name.charAt(0).toUpperCase()}</span>}
      src={sourceIconSrc}
      {...props}
    />
  );
}
