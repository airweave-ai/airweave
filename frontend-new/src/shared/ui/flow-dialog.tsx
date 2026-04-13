import * as React from 'react';
import { IconX } from '@tabler/icons-react';

import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { Dialog, DialogContent } from '@/shared/ui/dialog';

function FlowDialog({ ...props }: React.ComponentProps<typeof Dialog>) {
  return <Dialog {...props} />;
}

function FlowDialogContent({
  className,
  ...props
}: Omit<React.ComponentProps<typeof DialogContent>, 'showCloseButton'>) {
  return (
    <DialogContent
      showCloseButton={false}
      className={cn(
        'h-[min(54rem,calc(100vh-1rem))] max-w-[min(84rem,calc(100vw-1rem))] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden border-border bg-background p-0 text-foreground [view-transition-name:app-dialog-transition] sm:max-w-[min(84rem,calc(100vw-2rem))]',
        className,
      )}
      {...props}
    />
  );
}

function FlowDialogHeader({
  children,
  className,
  onClose,
  ...props
}: React.ComponentProps<'header'> & {
  onClose: () => void;
}) {
  return (
    <header
      data-slot="flow-dialog-header"
      className={cn(
        'flex items-center justify-between gap-6 border-b border-border px-6 py-4',
        className,
      )}
      {...props}
    >
      <div className="min-w-0 flex-1">{children}</div>

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

export {
  FlowDialog,
  FlowDialogAside,
  FlowDialogBody,
  FlowDialogContent,
  FlowDialogHeader,
  FlowDialogMain,
};
