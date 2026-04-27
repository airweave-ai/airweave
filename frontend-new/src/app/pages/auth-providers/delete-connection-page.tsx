import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRouteApi } from '@tanstack/react-router';
import { FolderX } from 'lucide-react';
import {
  useDeleteAuthProviderConnectionMutation,
  useGetAuthProviderConnectionQueryOptions,
} from '@/features/auth-providers';
import { ErrorState } from '@/shared/components/error-state';
import { LoadingState } from '@/shared/components/loading-state';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
} from '@/shared/ui/alert-dialog';
import { Spinner } from '@/shared/ui/spinner';

const routeApi = getRouteApi(
  '/_authenticated/_app/auth-providers/connections/$readableId/delete',
);

export function AuthProviderConnectionDeletePage() {
  const navigate = routeApi.useNavigate();
  const { readableId } = routeApi.useParams();
  const connectionQueryOptions = useGetAuthProviderConnectionQueryOptions({
    readableId,
  });
  const {
    data: connection,
    error: connectionError,
    isPending: isConnectionPending,
    refetch: refetchConnection,
  } = useQuery(connectionQueryOptions);
  const deleteConnectionMutation = useDeleteAuthProviderConnectionMutation();

  const handleClose = React.useCallback(() => {
    if (deleteConnectionMutation.isPending) {
      return;
    }

    void navigate({
      to: '/auth-providers',
      viewTransition: true,
    });
  }, [deleteConnectionMutation.isPending, navigate]);

  const handleDelete = React.useCallback(async () => {
    if (!connection) {
      return;
    }

    await deleteConnectionMutation.mutateAsync({
      path: {
        readable_id: connection.readable_id,
      },
    });
    handleClose();
  }, [connection, deleteConnectionMutation, handleClose]);

  let content: React.ReactNode = null;

  if (!connection && isConnectionPending) {
    content = (
      <LoadingState
        className="min-h-36 rounded-none border-0 p-0"
        description="Fetching auth provider connection."
        title="Loading connection"
      />
    );
  } else if (!connection || connectionError) {
    content = (
      <ErrorState
        className="min-h-36 rounded-none border-0 p-0"
        description="There was a problem loading this auth provider connection."
        onRetry={() => {
          void refetchConnection();
        }}
        retryLabel="Retry"
        title="We couldn't load this connection"
      />
    );
  } else {
    content = (
      <>
        <AlertDialogHeader className="">
          <AlertDialogMedia className="mb-0 bg-destructive/10 text-destructive">
            <FolderX className="size-6" />
          </AlertDialogMedia>
          <div className="space-y-1.5">
            <AlertDialogTitle className="">Delete connection</AlertDialogTitle>
            <AlertDialogDescription className="">
              This will permanently delete {connection.name}. You cannot undo
              this action.
            </AlertDialogDescription>
          </div>
        </AlertDialogHeader>

        <AlertDialogFooter>
          <AlertDialogCancel
            disabled={deleteConnectionMutation.isPending}
            onClick={handleClose}
          >
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={deleteConnectionMutation.isPending}
            variant="destructive"
            onClick={(event) => {
              event.preventDefault();
              void handleDelete();
            }}
          >
            Delete
            {deleteConnectionMutation.isPending ? (
              <Spinner className="size-4" />
            ) : null}
          </AlertDialogAction>
        </AlertDialogFooter>
      </>
    );
  }

  return (
    <AlertDialog
      open
      onOpenChange={(open) => {
        if (!open) {
          handleClose();
        }
      }}
    >
      <AlertDialogContent
        className="bg-background [view-transition-name:app-dialog-transition] sm:max-w-80"
        size="sm"
      >
        {content}
      </AlertDialogContent>
    </AlertDialog>
  );
}
