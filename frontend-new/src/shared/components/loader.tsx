import * as React from 'react';

import { Spinner } from '../ui/spinner';
import { cn } from '@/shared/tailwind/cn';

export function Loader({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn(
        'flex h-full w-full items-center justify-center',
        className,
      )}
      {...props}
    >
      <Spinner className="size-8" />
    </div>
  );
}
