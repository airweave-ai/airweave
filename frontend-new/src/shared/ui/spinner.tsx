import { LoaderCircle } from 'lucide-react';
import type { LucideProps } from 'lucide-react';

import { cn } from '@/shared/tailwind/cn';

function Spinner({ className, ...props }: LucideProps) {
  return (
    <LoaderCircle
      aria-hidden="true"
      data-slot="spinner"
      className={cn('animate-spin', className)}
      {...props}
    />
  );
}

export { Spinner };
