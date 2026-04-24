import type { ComponentProps } from 'react';
import { BrandIcon } from '@/shared/components/brand-icon';
import { getAuthProviderIconUrl } from '@/shared/icons/get-auth-provider-icon-url';
import { cn } from '../tailwind/cn';

interface AuthProviderIconProps extends ComponentProps<'div'> {
  name: string;
  shortName?: string;
}

export function AuthProviderIcon({
  className,
  name,
  shortName,
  ...props
}: AuthProviderIconProps) {
  const authProviderIconSrc = shortName
    ? getAuthProviderIconUrl(shortName)
    : null;

  return (
    <BrandIcon
      className={cn('rounded-xs', className)}
      fallback={<span>{name.charAt(0).toUpperCase()}</span>}
      src={authProviderIconSrc}
      {...props}
    />
  );
}
