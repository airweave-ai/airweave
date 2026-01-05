/**
 * Global dialogs that can be triggered from anywhere in the app
 */

import {
  AddSourceDialog,
  CreateCollectionDialog,
} from "@/features/collections";
import { useOrg } from "@/lib/org-context";
import { useAddSourceStore } from "@/stores/add-source-store";
import { useCreateCollectionStore } from "@/stores/create-collection-store";

export function GlobalDialogs() {
  const { organization } = useOrg();
  const { isOpen: isCreateOpen, close: closeCreate } =
    useCreateCollectionStore();
  const { isOpen: isAddSourceOpen, close: closeAddSource } =
    useAddSourceStore();

  if (!organization) return null;

  return (
    <>
      <CreateCollectionDialog
        open={isCreateOpen}
        onOpenChange={(open) => {
          if (!open) closeCreate();
        }}
        orgId={organization.id}
      />
      <AddSourceDialog
        open={isAddSourceOpen}
        onOpenChange={(open) => {
          if (!open) closeAddSource();
        }}
      />
    </>
  );
}
