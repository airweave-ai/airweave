import { SettingsSidebar } from './settings-sidebar';

import type { SettingsPage } from '@/app/layouts/app-search';
import { AppDialogCloseButton } from '@/shared/components/app-dialog-close-button';
import { AppDialogContent } from '@/shared/components/app-dialog-content';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';

type SettingsDialogProps = {
  page: SettingsPage;
  onClose: () => void;
};

const pageContent: Record<
  SettingsPage,
  { title: string; description: string; placeholder: string }
> = {
  account: {
    title: 'Account',
    description: 'Manage your account details, like avatar or display name',
    placeholder: 'Account',
  },
  people: {
    title: 'People',
    description: 'Manage organization members',
    placeholder: 'People',
  },
  usage: {
    title: 'Usage',
    description: 'Review organization usage',
    placeholder: 'Usage',
  },
  billing: {
    title: 'Billing',
    description: 'Manage plan and billing',
    placeholder: 'Billing',
  },
};

function SettingsDialog({ page, onClose }: SettingsDialogProps) {
  const content = pageContent[page];

  return (
    <AppDialogContent className="grid grid-rows-[auto_minmax(0,1fr)] md:grid-cols-[16rem_minmax(0,1fr)] md:grid-rows-1">
      <SettingsSidebar page={page} />

      <section className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)]">
        <header className="flex items-center justify-between gap-6 px-6 py-4">
          <div className="min-w-0 space-y-1">
            <DialogTitle className="text-xl font-semibold">
              {content.title}
            </DialogTitle>
            <DialogDescription className="font-mono">
              {content.description}
            </DialogDescription>
          </div>
          <AppDialogCloseButton onClick={onClose} />
        </header>

        <div className="min-h-0 overflow-y-auto px-6 pb-6">
          <div className="flex min-h-40 items-center justify-center rounded-lg border bg-foreground/[0.03] p-6 text-muted-foreground shadow-xs">
            {content.placeholder}
          </div>
        </div>
      </section>
    </AppDialogContent>
  );
}

export { SettingsDialog };
