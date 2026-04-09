import { getRouteApi, useNavigate } from '@tanstack/react-router';
import * as z from 'zod';
import { CreateCollectionDialogScreen } from '@/features/collections';
import { FlowDialog, FlowDialogContent } from '@/shared/ui/flow-dialog';

export const appDialogSearchSchema = z.object({
  type: z.literal('create-collection'),
});

export const appSearchSchema = z.object({
  dialog: appDialogSearchSchema.optional(),
});

export type AppSearch = z.infer<typeof appSearchSchema>;

const routeApi = getRouteApi('/_authenticated/_app');

export function AppDialog() {
  const navigate = useNavigate();
  const { dialog } = routeApi.useSearch();

  const handleClose = () => removeDialogSearchParams();

  const removeDialogSearchParams = () =>
    void navigate({
      replace: true,
      search: ((prev: Record<string, unknown>) => ({
        ...prev,
        dialog: undefined,
      })) as never,
      viewTransition: true,
    });

  return (
    <FlowDialog
      open={Boolean(dialog)}
      onOpenChange={(nextOpen) => !nextOpen && handleClose()}
    >
      <FlowDialogContent>
        {dialog?.type === 'create-collection' ? (
          <CreateCollectionDialogScreen
            onClose={handleClose}
            onCreated={(collection) =>
              void navigate({
                params: { collectionId: collection.readable_id },
                replace: true,
                to: '/collections/$collectionId/connect-source',
              })
            }
          />
        ) : null}
      </FlowDialogContent>
    </FlowDialog>
  );
}
