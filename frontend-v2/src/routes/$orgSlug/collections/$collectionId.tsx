import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createFileRoute,
  useLocation,
  useNavigate,
} from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { usePageHeader } from "@/components/ui/page-header";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";
import {
  AddSourceDialog,
  CollectionDetailCode,
  CollectionDetailDocs,
  CollectionDetailHelp,
  CollectionHeader,
  DeleteCollectionDialog,
  SourceConnectionsList,
  SourceConnectionStateView,
} from "@/features/collections";
import { Search } from "@/features/search";
import {
  deleteCollection,
  fetchCollection,
  fetchSourceConnections,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";
import { useAddSourceStore } from "@/stores/add-source-store";
import type { CollectionNavigationState } from "@/types/navigation";

export const Route = createFileRoute("/$orgSlug/collections/$collectionId")({
  component: CollectionDetailPage,
});

function CollectionDetailPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { getAccessTokenSilently } = useAuth0();
  const { organization, getOrgSlug } = useOrg();
  const queryClient = useQueryClient();
  const params = Route.useParams();
  const collectionId = params.collectionId;

  if (!organization) {
    throw new Error("Organization context is required but not available");
  }
  const orgId = organization.id;
  const orgSlug = getOrgSlug(organization);

  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showAddSourceDialog, setShowAddSourceDialog] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState<
    string | null
  >(null);

  // Prevents re-opening the dialog on re-renders after processing navigation state
  const processedNavState = useRef(false);

  const openAddSource = useAddSourceStore((s) => s.open);

  const {
    data: collection,
    isLoading: isLoadingCollection,
    error: collectionError,
    refetch: refetchCollection,
  } = useQuery({
    queryKey: queryKeys.collections.detail(orgId, collectionId),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchCollection(token, orgId, collectionId);
    },
  });

  const {
    data: sourceConnections = [],
    error: connectionsError,
    refetch: refetchConnections,
  } = useQuery({
    queryKey: queryKeys.sourceConnections.list(orgId, collectionId),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSourceConnections(token, orgId, collectionId);
    },
    enabled: !!collection,
  });

  const selectedConnection = useMemo(() => {
    if (!sourceConnections.length) return null;
    if (selectedConnectionId) {
      const found = sourceConnections.find(
        (c) => c.id === selectedConnectionId
      );
      if (found) return found;
    }
    return sourceConnections[0];
  }, [sourceConnections, selectedConnectionId]);

  useEffect(() => {
    if (sourceConnections.length > 0 && !selectedConnectionId) {
      setSelectedConnectionId(sourceConnections[0].id);
    }
  }, [sourceConnections, selectedConnectionId]);

  // Handle pre-selected source from navigation state ("Start from a Source" flow)
  useEffect(() => {
    if (processedNavState.current || !collection) return;

    const navState = location.state as CollectionNavigationState | undefined;
    if (navState?.addSource) {
      processedNavState.current = true;
      openAddSource(
        collection.readable_id,
        collection.name,
        navState.addSource
      );
      setShowAddSourceDialog(true);

      navigate({
        to: location.pathname,
        replace: true,
      });
    }
  }, [collection, location.state, location.pathname, navigate, openAddSource]);

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return deleteCollection(token, orgId, collectionId);
    },
    onSuccess: () => {
      toast.success("Collection deleted successfully");
      queryClient.invalidateQueries({
        queryKey: queryKeys.collections.all(orgId),
      });
      navigate({ to: `/${orgSlug}/collections` });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to delete collection"
      );
    },
  });

  usePageHeader({
    title: collection?.name || "Loading...",
    description: collection?.readable_id || "",
  });

  useRightSidebarContent({
    docs: <CollectionDetailDocs />,
    code: <CollectionDetailCode collectionId={collectionId} />,
    help: <CollectionDetailHelp />,
  });

  const handleReload = useCallback(() => {
    refetchCollection();
    refetchConnections();
  }, [refetchCollection, refetchConnections]);

  const handleAddSource = useCallback(() => {
    if (collection) {
      openAddSource(collection.readable_id, collection.name);
      setShowAddSourceDialog(true);
    }
  }, [collection, openAddSource]);

  if (isLoadingCollection) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <LoadingState />
      </div>
    );
  }

  if (collectionError || connectionsError) {
    return (
      <div className="p-6">
        <ErrorState
          error={
            collectionError instanceof Error
              ? collectionError
              : connectionsError instanceof Error
                ? connectionsError
                : "Failed to load collection"
          }
        />
      </div>
    );
  }

  if (!collection) {
    return (
      <div className="p-6">
        <ErrorState error="Collection not found" />
      </div>
    );
  }

  return (
    <div className="container mx-auto flex max-w-[1000px] flex-col items-center py-6">
      <CollectionHeader
        collection={collection}
        sourceConnections={sourceConnections}
        onReload={handleReload}
        onDelete={() => setShowDeleteDialog(true)}
      />

      <div className="mt-10 w-full">
        <Search
          collectionReadableId={collection.readable_id}
          disabled={sourceConnections.length === 0}
          disabledReason="no_sources"
        />
      </div>

      <div className="mt-8 w-full">
        <SourceConnectionsList
          sourceConnections={sourceConnections}
          selectedConnectionId={selectedConnectionId}
          onSelectConnection={setSelectedConnectionId}
          onAddSource={handleAddSource}
        />
      </div>

      {selectedConnection && (
        <div className="mt-4 w-full">
          <SourceConnectionStateView
            key={selectedConnection.id}
            sourceConnection={selectedConnection}
            onConnectionDeleted={() => {
              setSelectedConnectionId(null);
              refetchConnections();
            }}
            onConnectionUpdated={refetchConnections}
          />
        </div>
      )}

      <DeleteCollectionDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        onConfirm={() => deleteMutation.mutate()}
        collectionReadableId={collection.readable_id}
        isDeleting={deleteMutation.isPending}
      />

      <AddSourceDialog
        open={showAddSourceDialog}
        onOpenChange={(open) => {
          setShowAddSourceDialog(open);
          if (!open) {
            refetchConnections();
          }
        }}
      />
    </div>
  );
}
