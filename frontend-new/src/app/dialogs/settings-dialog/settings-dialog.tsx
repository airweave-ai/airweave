import { SettingsDialogAccountPage } from './settings-dialog-account-page';
import { SettingsDialogBillingPage } from './settings-dialog-billing-page';
import { SettingsDialogPeoplePage } from './settings-dialog-people-page';
import { SettingsDialogUsagePage } from './settings-dialog-usage-page';
import { SettingsSidebar } from './settings-sidebar';

import type * as React from 'react';
import type { SettingsPage } from '@/app/layouts/app-search';
import { AppDialogContent } from '@/shared/components/app-dialog-content';

type SettingsDialogProps = {
  page: SettingsPage;
  onClose: () => void;
};

const pageComponents: Record<
  SettingsPage,
  React.ComponentType<{ onClose: () => void }>
> = {
  account: SettingsDialogAccountPage,
  people: SettingsDialogPeoplePage,
  usage: SettingsDialogUsagePage,
  billing: SettingsDialogBillingPage,
};

function SettingsDialog({ page, onClose }: SettingsDialogProps) {
  const Page = pageComponents[page];

  return (
    <AppDialogContent className="grid grid-rows-[auto_minmax(0,1fr)] md:grid-cols-[16rem_minmax(0,1fr)] md:grid-rows-1">
      <SettingsSidebar page={page} />
      <Page onClose={onClose} />
    </AppDialogContent>
  );
}

export { SettingsDialog };
