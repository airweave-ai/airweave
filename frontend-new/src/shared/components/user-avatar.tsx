import type { ComponentProps } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '../ui/avatar';
import { cn } from '../tailwind/cn';

interface UserAvatarProps extends Omit<
  ComponentProps<typeof Avatar>,
  'children'
> {
  email: string;
  fallback?: string;
  name?: string | null;
  picture?: string | null;
}

function getUserInitials(label: string) {
  return label[0]?.toUpperCase();
}

export function UserAvatar({
  className,
  email,
  fallback = 'U',
  name,
  picture,
  ...props
}: UserAvatarProps) {
  const initials = getUserInitials(name ?? email) || fallback;
  const label = name ?? email;

  return (
    <Avatar className={cn(className)} {...props}>
      <AvatarImage alt={label} src={picture ?? undefined} />
      <AvatarFallback>{initials}</AvatarFallback>
    </Avatar>
  );
}
