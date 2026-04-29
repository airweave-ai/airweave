import * as React from 'react';

import { AppDialogCloseButton } from '@/shared/components/app-dialog-close-button';
import { AppDialogContent } from '@/shared/components/app-dialog-content';
import { cn } from '@/shared/tailwind/cn';
import { Dialog, DialogFooter } from '@/shared/ui/dialog';

function FlowDialog({ ...props }: React.ComponentProps<typeof Dialog>) {
  return <Dialog {...props} />;
}

function FlowDialogContent({
  className,
  size,
  ...props
}: React.ComponentProps<typeof AppDialogContent>) {
  return (
    <AppDialogContent
      size={size}
      className={cn(
        'grid grid-rows-[auto_minmax(0,1fr)] has-[>[data-slot=flow-dialog-footer]]:grid-rows-[auto_auto_minmax(0,1fr)_auto]',
        className,
      )}
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

      <div
        className="min-w-0 flex-1 data-[align=center]:text-center"
        data-align={align}
      >
        {children}
      </div>

      <AppDialogCloseButton onClick={onClose} />
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
        'mx-0 mb-0 flex-col-reverse items-stretch justify-between gap-2 rounded-none border-t bg-muted/30 p-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4',
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
