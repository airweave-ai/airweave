/**
 * Global dialogs that can be triggered from anywhere in the app
 */

import { useNavigate } from "@tanstack/react-router";

import { CreateCollectionDialog } from "@/features/collections";
import { type Collection } from "@/lib/api";
import { useOrg } from "@/lib/org-context";
import { useCreateCollectionStore } from "@/stores/create-collection-store";
import type { CollectionNavigationState } from "@/types/navigation";

export function GlobalDialogs() {
  const navigate = useNavigate();
  const { organization, getOrgSlug } = useOrg();
  const {
    isOpen: isCreateOpen,
    close: closeCreate,
    preSelectedSource,
  } = useCreateCollectionStore();
  const clearPreSelectedSource = useCreateCollectionStore(
    (s) => s.clearPreSelectedSource
  );

  if (!organization) return null;

  const orgSlug = getOrgSlug(organization);

  // Handle collection creation success
  const handleCollectionCreated = (collection: Collection) => {
    // Get the pre-selected source (if any) and clear it
    const sourceToAdd = preSelectedSource;
    clearPreSelectedSource();

    // Build navigation state if we have a pre-selected source
    const state: CollectionNavigationState | undefined = sourceToAdd
      ? { addSource: sourceToAdd }
      : undefined;

    // Navigate to the new collection
    // State is passed as HistoryState which accepts any serializable object
    navigate({
      to: `/${orgSlug}/collections/${collection.readable_id}`,
      state: state as Parameters<typeof navigate>[0]["state"],
    });
  };

  return (
    <CreateCollectionDialog
      open={isCreateOpen}
      onOpenChange={(open) => {
        if (!open) closeCreate();
      }}
      orgId={organization.id}
      onSuccess={handleCollectionCreated}
    />
  );
}
