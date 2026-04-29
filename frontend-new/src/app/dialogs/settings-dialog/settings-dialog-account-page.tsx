import { SettingsDialogLayout } from './settings-dialog-layout';

import {
  AvatarForm,
  DeleteAccountForm,
  UsernameForm,
} from '@/features/account';
import { OrganizationsCard } from '@/features/organizations';
import { useAppSession } from '@/shared/session';

type SettingsDialogAccountPageProps = {
  onClose: () => void;
};

function SettingsDialogAccountPage({
  onClose,
}: SettingsDialogAccountPageProps) {
  const { organizations, viewer } = useAppSession();

  return (
    <SettingsDialogLayout
      title="Account"
      description="Manage your account details, like avatar or display name"
      onClose={onClose}
      className="space-y-2"
    >
      <AvatarForm viewer={viewer} />
      <UsernameForm viewer={viewer} />
      <OrganizationsCard organizations={organizations} />
      <DeleteAccountForm />
    </SettingsDialogLayout>
  );
}

export { SettingsDialogAccountPage };
