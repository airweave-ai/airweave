import * as React from 'react';
import { cva } from 'class-variance-authority';
import type { VariantProps } from 'class-variance-authority';

import { cn } from '@/shared/tailwind/cn';
import { DialogContent } from '@/shared/ui/dialog';

const appDialogContentVariants = cva(
  'h-[min(54rem,calc(100vh-1rem))] gap-0 overflow-hidden bg-background p-0 text-foreground ring-0 [view-transition-name:app-dialog-transition]',
  {
    variants: {
      size: {
        default:
          'max-w-[min(84rem,calc(100vw-1rem))] sm:max-w-[min(84rem,calc(100vw-2rem))]',
        sm: 'max-w-[min(64rem,calc(100vw-1rem))] sm:max-w-[min(64rem,calc(100vw-2rem))]',
      },
    },
    defaultVariants: {
      size: 'default',
    },
  },
);

function AppDialogContent({
  className,
  size,
  ...props
}: Omit<React.ComponentProps<typeof DialogContent>, 'showCloseButton'> &
  VariantProps<typeof appDialogContentVariants>) {
  return (
    <DialogContent
      showCloseButton={false}
      className={cn(appDialogContentVariants({ size }), className)}
      {...props}
    />
  );
}

export { AppDialogContent, appDialogContentVariants };
