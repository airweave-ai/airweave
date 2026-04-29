import { SettingsDialogPlaceholderPage } from './settings-dialog-placeholder-page';

type SettingsDialogUsagePageProps = {
  onClose: () => void;
};

function SettingsDialogUsagePage({ onClose }: SettingsDialogUsagePageProps) {
  return (
    <SettingsDialogPlaceholderPage
      title="Usage"
      description="Review organization usage"
      placeholder="Usage"
      onClose={onClose}
    />
  );
}

export { SettingsDialogUsagePage };
