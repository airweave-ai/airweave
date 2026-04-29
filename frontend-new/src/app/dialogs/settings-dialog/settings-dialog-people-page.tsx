import { SettingsDialogPlaceholderPage } from './settings-dialog-placeholder-page';

type SettingsDialogPeoplePageProps = {
  onClose: () => void;
};

function SettingsDialogPeoplePage({ onClose }: SettingsDialogPeoplePageProps) {
  return (
    <SettingsDialogPlaceholderPage
      title="People"
      description="Manage organization members"
      placeholder="People"
      onClose={onClose}
    />
  );
}

export { SettingsDialogPeoplePage };
