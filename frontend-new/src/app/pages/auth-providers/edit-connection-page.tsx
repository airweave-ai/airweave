import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRouteApi } from '@tanstack/react-router';
import type { AuthProviderConnection } from '@/shared/api';
import {
  EditAuthProviderConnectionForm,
  useAuthProviderConnectionUpdateSubmission,
  useGetAuthProviderConnectionQueryOptions,
  useGetAuthProviderDetailQueryOptions,
} from '@/features/auth-providers';
import { ErrorState } from '@/shared/components/error-state';
import { LoadingState } from '@/shared/components/loading-state';
import { Button } from '@/shared/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog';
import { Spinner } from '@/shared/ui/spinner';

const routeApi = getRouteApi(
  '/_authenticated/_app/auth-providers/connections/$readableId/edit',
);

export function AuthProviderConnectionEditPage() {
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

  const handleClose = React.useCallback(() => {
    void navigate({
      to: '/auth-providers',
      viewTransition: true,
    });
  }, [navigate]);

  if (!connection && isConnectionPending) {
    return (
      <AuthProviderConnectionEditDialog onClose={handleClose}>
        <LoadingState
          className="min-h-52 rounded-none border-0 p-0"
          description="Fetching auth provider connection."
          title="Loading connection"
        />
      </AuthProviderConnectionEditDialog>
    );
  }

  if (!connection || connectionError) {
    return (
      <AuthProviderConnectionEditDialog onClose={handleClose}>
        <ErrorState
          className="min-h-52 rounded-none border-0 p-0"
          description="There was a problem loading this auth provider connection."
          onRetry={() => {
            void refetchConnection();
          }}
          retryLabel="Retry"
          title="We couldn't load this connection"
        />
      </AuthProviderConnectionEditDialog>
    );
  }

  return (
    <AuthProviderConnectionLoadedEditDialog
      connection={connection}
      navigateToAuthProviders={handleClose}
    />
  );
}

function AuthProviderConnectionLoadedEditDialog({
  connection,
  navigateToAuthProviders,
}: {
  connection: AuthProviderConnection;
  navigateToAuthProviders: () => void;
}) {
  const updateSubmission = useAuthProviderConnectionUpdateSubmission({
    connection,
  });

  const handleClose = React.useCallback(() => {
    if (updateSubmission.isPending) {
      return;
    }

    navigateToAuthProviders();
  }, [navigateToAuthProviders, updateSubmission.isPending]);

  return (
    <AuthProviderConnectionEditDialog onClose={handleClose}>
      <AuthProviderConnectionEditContent
        connection={connection}
        onClose={handleClose}
        updateSubmission={updateSubmission}
      />
    </AuthProviderConnectionEditDialog>
  );
}

function AuthProviderConnectionEditDialog({
  children,
  onClose,
}: React.PropsWithChildren<{
  onClose: () => void;
}>) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <DialogContent className="bg-background [view-transition-name:app-dialog-transition] sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Edit Connection</DialogTitle>
        </DialogHeader>

        {children}
      </DialogContent>
    </Dialog>
  );
}

function AuthProviderConnectionEditContent({
  connection,
  onClose,
  updateSubmission,
}: {
  connection: AuthProviderConnection;
  onClose: () => void;
  updateSubmission: ReturnType<
    typeof useAuthProviderConnectionUpdateSubmission
  >;
}) {
  const authProviderQueryOptions = useGetAuthProviderDetailQueryOptions({
    shortName: connection.short_name,
  });
  const {
    data: authProvider,
    error: authProviderError,
    isPending: isAuthProviderPending,
    refetch: refetchAuthProvider,
  } = useQuery(authProviderQueryOptions);
  const formId = React.useId();

  const handleSubmit = React.useCallback(
    async (...args: Parameters<typeof updateSubmission.handleSubmit>) => {
      await updateSubmission.handleSubmit(...args);
      onClose();
    },
    [onClose, updateSubmission],
  );

  const handleValueChange = React.useCallback(() => {
    updateSubmission.reset();
  }, [updateSubmission]);

  if (!authProvider && isAuthProviderPending) {
    return (
      <LoadingState
        className="min-h-52 rounded-none border-0 p-0"
        description="Fetching auth provider fields for this connection."
        title="Loading auth provider"
      />
    );
  }

  if (!authProvider || authProviderError) {
    return (
      <ErrorState
        className="min-h-52 rounded-none border-0 p-0"
        description="There was a problem loading this auth provider's connection fields."
        onRetry={() => {
          void refetchAuthProvider();
        }}
        retryLabel="Retry"
        title="We couldn't load this auth provider"
      />
    );
  }

  return (
    <>
      <EditAuthProviderConnectionForm
        key={connection.id}
        authProvider={authProvider}
        connection={connection}
        formId={formId}
        isPending={updateSubmission.isPending}
        onSubmit={handleSubmit}
        onValueChange={handleValueChange}
        submitError={updateSubmission.submitError}
      />

      <DialogFooter>
        <Button
          className="w-full sm:w-[120px] sm:shrink-0"
          disabled={updateSubmission.isPending}
          type="button"
          variant="outline"
          onClick={onClose}
          size="lg"
        >
          Cancel
        </Button>
        <Button
          className="w-full sm:flex-1"
          disabled={updateSubmission.isPending}
          form={formId}
          type="submit"
          size="lg"
        >
          Save
          {updateSubmission.isPending ? <Spinner className="size-4" /> : null}
        </Button>
      </DialogFooter>
    </>
  );
}
