import { getRouteApi, useNavigate } from '@tanstack/react-router';
import * as z from 'zod';
import { CreateCollectionDialog } from '@/features/collections/components/create-collection-dialog';

export const appDialogSearchSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('create-collection'),
  }),
]);

export const appSearchSchema = z.object({
  dialog: appDialogSearchSchema.optional(),
});

const routeApi = getRouteApi('/_authenticated/_app');

export function AppDialog() {
  const navigate = useNavigate();
  const { dialog } = routeApi.useSearch();

  switch (dialog?.type) {
    case 'create-collection':
      return (
        <CreateCollectionDialog
          onClose={() =>
            void navigate({
              replace: true,
              search: ((prev: Record<string, unknown>) => ({
                ...prev,
                dialog: undefined,
              })) as never,
            })
          }
          onCreated={(collection) =>
            void navigate({
              params: { collectionId: collection.readable_id },
              replace: true,
              to: '/collections/$collectionId',
            })
          }
        />
      );
    default:
      return null;
  }
}
