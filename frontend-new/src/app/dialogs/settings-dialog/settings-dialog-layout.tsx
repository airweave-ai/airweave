import type * as React from 'react';

import { AppDialogCloseButton } from '@/shared/components/app-dialog-close-button';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';
import { cn } from '@/shared/tailwind/cn';

type SettingsDialogLayoutProps = React.PropsWithChildren<{
  description: string;
  onClose: () => void;
  title: string;
  className?: string;
}>;

function SettingsDialogLayout({
  children,
  description,
  onClose,
  title,
  className,
}: SettingsDialogLayoutProps) {
  return (
    <section className="grid h-full grid-rows-[auto_minmax(0,1fr)]">
      <header className="flex items-center justify-between gap-6 px-6 py-4">
        <div className="min-w-0 space-y-1">
          <DialogTitle className="text-xl font-semibold">{title}</DialogTitle>
          <DialogDescription className="font-mono">
            {description}
          </DialogDescription>
        </div>
        <AppDialogCloseButton onClick={onClose} />
      </header>

      <div className={cn('min-h-0 overflow-y-auto px-6 pt-2 pb-6', className)}>
        {children}
      </div>
    </section>
  );
}

export { SettingsDialogLayout };
