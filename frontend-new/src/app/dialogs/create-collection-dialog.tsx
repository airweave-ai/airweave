import { useNavigate } from '@tanstack/react-router';

import { CreateCollectionDialogScreen } from '@/features/collections';

type CreateCollectionAppDialogProps = {
  onClose: () => void;
};

function CreateCollectionAppDialog({
  onClose,
}: CreateCollectionAppDialogProps) {
  const navigate = useNavigate();

  return (
    <CreateCollectionDialogScreen
      onClose={onClose}
      onCreated={(collection) =>
        void navigate({
          params: { collectionId: collection.readable_id },
          replace: true,
          to: '/collections/$collectionId/connect-source',
        })
      }
    />
  );
}

export { CreateCollectionAppDialog };
