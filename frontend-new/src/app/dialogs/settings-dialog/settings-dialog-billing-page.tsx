import { SettingsDialogPlaceholderPage } from './settings-dialog-placeholder-page';

type SettingsDialogBillingPageProps = {
  onClose: () => void;
};

function SettingsDialogBillingPage({ onClose }: SettingsDialogBillingPageProps) {
  return (
    <SettingsDialogPlaceholderPage
      title="Billing"
      description="Manage plan and billing"
      placeholder="Billing"
      onClose={onClose}
    />
  );
}

export { SettingsDialogBillingPage };
