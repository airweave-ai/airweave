import * as React from 'react';
import { getRouteApi } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import type { ConnectAuthProviderFormOutput } from '@/features/auth-providers';
import {
  ConnectAuthProviderForm,
  useConnectAuthProviderMutation,
  useGetAuthProviderDetailQueryOptions,
} from '@/features/auth-providers';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog';
import { getApiErrorMessage } from '@/shared/api';
import { ErrorState } from '@/shared/components/error-state';
import { LoadingState } from '@/shared/components/loading-state';
import { Button } from '@/shared/ui/button';
import { Spinner } from '@/shared/ui/spinner';

const routeApi = getRouteApi(
  '/_authenticated/_app/auth-providers/$shortName/connect',
);

export function AuthProviderConnectPage() {
  const navigate = routeApi.useNavigate();
  const { shortName } = routeApi.useParams();
  const authProviderQueryOptions = useGetAuthProviderDetailQueryOptions({
    shortName,
  });
  const connectAuthProviderMutation = useConnectAuthProviderMutation();
  const {
    data: authProvider,
    isPending: isAuthProviderPending,
    refetch: refetchAuthProvider,
  } = useQuery(authProviderQueryOptions);
  const submitError = getApiErrorMessage(
    connectAuthProviderMutation.error,
    'Could not connect auth provider.',
  );
  const formId = React.useId();

  const handleClose = React.useCallback(() => {
    if (connectAuthProviderMutation.isPending) {
      return;
    }

    void navigate({
      to: '/auth-providers',
      viewTransition: true,
    });
  }, [connectAuthProviderMutation.isPending, navigate]);

  const handleSubmit = React.useCallback(
    async (values: ConnectAuthProviderFormOutput) => {
      await connectAuthProviderMutation.mutateAsync({
        body: {
          auth_fields: values.auth_fields,
          name: values.name,
          readable_id: values.readable_id,
          short_name: shortName,
        },
      });

      handleClose();
    },
    [connectAuthProviderMutation, handleClose, shortName],
  );

  const handleValueChange = React.useCallback(() => {
    if (!connectAuthProviderMutation.error) {
      return;
    }

    connectAuthProviderMutation.reset();
  }, [connectAuthProviderMutation]);

  let content: React.ReactNode = null;

  if (!authProvider && isAuthProviderPending) {
    content = (
      <LoadingState
        className="min-h-52 rounded-none border-0 p-0"
        description="Fetching auth provider fields for this connection."
        title="Loading auth provider"
      />
    );
  } else if (!authProvider) {
    content = (
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
  } else {
    content = (
      <>
        <ConnectAuthProviderForm
          key={authProvider.short_name}
          authProvider={authProvider}
          formId={formId}
          isPending={connectAuthProviderMutation.isPending}
          onSubmit={handleSubmit}
          onValueChange={handleValueChange}
          submitError={submitError}
        />

        <DialogFooter>
          <Button
            className="w-full sm:w-[120px] sm:shrink-0"
            disabled={connectAuthProviderMutation.isPending}
            type="button"
            variant="outline"
            onClick={handleClose}
            size="lg"
          >
            Cancel
          </Button>
          <Button
            className="w-full sm:flex-1"
            disabled={connectAuthProviderMutation.isPending}
            form={formId}
            type="submit"
            size="lg"
          >
            Connect
            {connectAuthProviderMutation.isPending ? (
              <Spinner className="size-4" />
            ) : null}
          </Button>
        </DialogFooter>
      </>
    );
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) {
          handleClose();
        }
      }}
    >
      <DialogContent className="bg-background [view-transition-name:app-dialog-transition] sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            Connect to {authProvider?.name ?? shortName}
          </DialogTitle>
        </DialogHeader>

        {content}
      </DialogContent>
    </Dialog>
  );
}
