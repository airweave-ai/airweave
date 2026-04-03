import { getAppIconUrl } from '@/shared/icons/get-app-icon-url';
import { cn } from '@/shared/tailwind/cn';

interface SourceIconProps {
  className?: string;
  name: string;
  shortName: string;
}

export function SourceIcon({ className, name, shortName }: SourceIconProps) {
  const sourceIconSrc = getAppIconUrl(shortName, 'color');

  return (
    <div
      className={cn(
        'flex size-5 shrink-0 items-center justify-center text-xs font-semibold',
        !sourceIconSrc && 'rounded-sm border',
        className,
      )}
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
