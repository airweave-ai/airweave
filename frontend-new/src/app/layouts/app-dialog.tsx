import { getRouteApi, useNavigate } from '@tanstack/react-router';
import { CreateCollectionAppDialog } from '@/app/dialogs/create-collection-dialog';
import { SettingsDialog } from '@/app/dialogs/settings-dialog';
import { FlowDialog } from '@/shared/components/flow-dialog';

const routeApi = getRouteApi('/_authenticated/_app');

export function AppDialog() {
  const navigate = useNavigate();
  const { dialog } = routeApi.useSearch();

  const handleClose = () => removeDialogSearchParams();

  const removeDialogSearchParams = () =>
    void navigate({
      to: '.',
      replace: true,
      search: (prev) => ({ ...prev, dialog: undefined }),
      viewTransition: true,
    });

  return (
    <FlowDialog
      open={Boolean(dialog)}
      onOpenChange={(nextOpen) => !nextOpen && handleClose()}
    >
      {dialog?.type === 'create-collection' ? (
        <CreateCollectionAppDialog onClose={handleClose} />
      ) : null}
      {dialog?.type === 'settings' ? (
        <SettingsDialog page={dialog.page} onClose={handleClose} />
      ) : null}
    </FlowDialog>
  );
}
