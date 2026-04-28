import * as React from 'react';
import { IconX } from '@tabler/icons-react';
import { cva } from 'class-variance-authority';
import type { VariantProps } from 'class-variance-authority';

import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { Dialog, DialogContent, DialogFooter } from '@/shared/ui/dialog';

function FlowDialog({ ...props }: React.ComponentProps<typeof Dialog>) {
  return <Dialog {...props} />;
}

const flowDialogContentVariants = cva(
  'h-[min(54rem,calc(100vh-1rem))] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden border-border bg-background p-0 text-foreground [view-transition-name:app-dialog-transition] has-[>[data-slot=flow-dialog-footer]]:grid-rows-[auto_auto_minmax(0,1fr)_auto]',
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

function FlowDialogContent({
  className,
  size,
  ...props
}: Omit<React.ComponentProps<typeof DialogContent>, 'showCloseButton'> &
  VariantProps<typeof flowDialogContentVariants>) {
  return (
    <DialogContent
      showCloseButton={false}
      className={cn(flowDialogContentVariants({ size }), className)}
      {...props}
    />
  );
}

function FlowDialogHeader({
  align = 'start',
  children,
  className,
  onClose,
  ...props
}: React.ComponentProps<'header'> & {
  align?: 'start' | 'center';
  onClose: () => void;
}) {
  return (
    <header
      data-slot="flow-dialog-header"
      className={cn(
        'flex items-center justify-between gap-6 border-b border-border px-6 py-4',
        align === 'center' && 'grid grid-cols-[2.25rem_1fr_2.25rem]',
        className,
      )}
      {...props}
    >
      {align === 'center' && <span aria-hidden className="size-9" />}

      <div className="min-w-0 flex-1 data-[align=center]:text-center" data-align={align}>
        {children}
      </div>

      <Button
        type="button"
        variant="outline"
        size="icon"
        className="bg-foreground/5 text-foreground hover:bg-foreground/10"
        onClick={onClose}
      >
        <IconX className="size-4" />
        <span className="sr-only">Close dialog</span>
      </Button>
    </header>
  );
}

function FlowDialogBody({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="flow-dialog-body"
      className={cn(
        'flex min-h-0 flex-1 flex-col divide-y divide-border overflow-y-auto lg:flex-row lg:divide-x lg:divide-y-0 lg:overflow-hidden',
        className,
      )}
      {...props}
    />
  );
}

function FlowDialogMain({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="flow-dialog-main"
      className={cn(
        'min-h-0 flex-none overflow-visible px-6 py-6 lg:flex-1 lg:overflow-y-auto',
        className,
      )}
      {...props}
    />
  );
}

function FlowDialogAside({
  className,
  ...props
}: React.ComponentProps<'aside'>) {
  return (
    <aside
      data-slot="flow-dialog-aside"
      className={cn(
        'w-full shrink-0 overflow-visible px-6 py-6 lg:w-80 lg:overflow-y-auto',
        className,
      )}
      {...props}
    />
  );
}

function FlowDialogFooter({
  className,
  ...props
}: React.ComponentProps<typeof DialogFooter>) {
  return (
    <DialogFooter
      data-slot="flow-dialog-footer"
      className={cn(
        'mx-0 mb-0 flex-col-reverse items-stretch justify-between gap-2 rounded-none border-t bg-muted/30 p-4 sm:flex-row sm:items-center sm:gap-4 sm:justify-between',
        className,
      )}
      {...props}
    />
  );
}

export {
  FlowDialog,
  FlowDialogAside,
  FlowDialogBody,
  FlowDialogContent,
  FlowDialogFooter,
  FlowDialogHeader,
  FlowDialogMain,
};
