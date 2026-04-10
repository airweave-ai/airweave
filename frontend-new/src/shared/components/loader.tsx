import * as React from 'react';

import { AirweaveLogo } from '../ui/airweave-logo';
import { cn } from '@/shared/tailwind/cn';

export function Loader({
  children,
  className,
  ...props
}: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn(
        'flex h-full min-h-0 w-full items-center justify-center',
        className,
      )}
      {...props}
    >
      <div className="flex flex-col items-center gap-4 px-4 text-center">
        <div className="airweave-loader-logo-intro">
          <AirweaveLogo
            aria-hidden="true"
            className="airweave-loader-rotate size-8 text-foreground"
          />
        </div>
        <p className="airweave-loader-text-intro font-mono text-sm text-muted-foreground">
          {children ?? 'Loading Airweave...'}
        </p>
      </div>
    </div>
  );
}
