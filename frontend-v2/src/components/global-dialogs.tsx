/**
 * Global dialogs that can be triggered from anywhere in the app
 */

import { CreateCollectionDialog } from "@/features/collections";
import { useOrg } from "@/lib/org-context";
import { useCreateCollectionStore } from "@/stores/create-collection-store";

export function GlobalDialogs() {
  const { organization } = useOrg();
  const { isOpen, close } = useCreateCollectionStore();

  if (!organization) return null;

  return (
    <CreateCollectionDialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      orgId={organization.id}
    />
  );
}
