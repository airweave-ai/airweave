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

  const handleCollectionCreated = (collection: Collection) => {
    const sourceToAdd = preSelectedSource;
    clearPreSelectedSource();

    const state: CollectionNavigationState | undefined = sourceToAdd
      ? { addSource: sourceToAdd }
      : undefined;

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
