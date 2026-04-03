import * as React from 'react';
import { getRouteApi, useNavigate } from '@tanstack/react-router';
import * as z from 'zod';
import { CreateCollectionDialogScreen } from '@/features/collections';
import {
  ConnectSourceDialogScreen,
  connectSourceStepSchema,
} from '@/features/source-connections';
import { FlowDialog, FlowDialogContent } from '@/shared/ui/flow-dialog';

export const appDialogSearchSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('create-collection'),
  }),
  z.object({
    state: connectSourceStepSchema,
    type: z.literal('connect-source'),
  }),
]);

export const appSearchSchema = z.object({
  dialog: appDialogSearchSchema.optional(),
});

const routeApi = getRouteApi('/_authenticated/_app');

export function AppDialog() {
  const navigate = useNavigate();
  const { dialog } = routeApi.useSearch();
  const [isOpen, setIsOpen] = React.useState(Boolean(dialog));

  React.useEffect(() => {
    if (dialog) {
      setIsOpen(true);
    }
  }, [dialog]);

  const handleClose = () => setIsOpen(false);

  const removeDialogSearchParam = () =>
    void navigate({
      replace: true,
      search: ((prev: Record<string, unknown>) => ({
        ...prev,
        dialog: undefined,
      })) as never,
    });

  return (
    <FlowDialog
      open={isOpen}
      onOpenChange={(nextOpen) => !nextOpen && handleClose()}
    >
      <FlowDialogContent
        onAnimationEnd={() => {
          if (!isOpen) {
            removeDialogSearchParam();
          }
        }}
      >
        {dialog?.type === 'create-collection' ? (
          <CreateCollectionDialogScreen
            onClose={handleClose}
            onCreated={(collection) =>
              void navigate({
                params: { collectionId: collection.readable_id },
                replace: true,
                search: {
                  dialog: {
                    state: {
                      collectionId: collection.readable_id,
                      step: 'source',
                    },
                    type: 'connect-source',
                  },
                },
                to: '/collections/$collectionId',
              })
            }
          />
        ) : dialog?.type === 'connect-source' ? (
          <ConnectSourceDialogScreen
            onClose={handleClose}
            onStepChange={(nextStep) =>
              void navigate({
                search: ((prev: Record<string, unknown>) => ({
                  ...prev,
                  dialog: {
                    state: nextStep,
                    type: 'connect-source',
                  },
                })) as never,
              })
            }
            step={dialog.state}
          />
        ) : null}
      </FlowDialogContent>
    </FlowDialog>
  );
}
