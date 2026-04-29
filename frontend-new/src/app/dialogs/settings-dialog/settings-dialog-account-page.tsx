import { SettingsDialogLayout } from './settings-dialog-layout';

import { AvatarForm } from '@/features/account/components/avatar-form';
import { UsernameForm } from '@/features/account/components/username-form';
import { useAppSession } from '@/shared/session';

type SettingsDialogAccountPageProps = {
  onClose: () => void;
};

function SettingsDialogAccountPage({
  onClose,
}: SettingsDialogAccountPageProps) {
  const { viewer } = useAppSession();

  return (
    <SettingsDialogLayout
      title="Account"
      description="Manage your account details, like avatar or display name"
      onClose={onClose}
      className="flex flex-col gap-2"
    >
      <AvatarForm viewer={viewer} />
      <UsernameForm viewer={viewer} />
    </SettingsDialogLayout>
  );
}

export { SettingsDialogAccountPage };
