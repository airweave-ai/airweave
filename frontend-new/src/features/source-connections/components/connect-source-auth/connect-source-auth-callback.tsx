import * as React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  invalidateSourceConnectionQueries,
  useGetSourceConnectionQueryOptions,
  useVerifySourceConnectionOAuthMutationOptions,
} from '../../api';
import { ConnectSourceStepLayoutContent } from '../connect-source-step-layout';
import {
  clearConnectSourceAuthClaimToken,
  getConnectSourceAuthClaimToken,
} from './connect-source-auth-storage';
import { ConnectSourceAuthError } from './connect-source-auth-error';
import type { SourceConnection } from '@/shared/api';
import { getApiErrorMessage } from '@/shared/api';
import { Loader } from '@/shared/components/loader';

interface ConnectSourceAuthCallbackProps {
  onClose: () => void;
  onVerified: (sourceConnection: SourceConnection) => Promise<void> | void;
  sourceConnection: SourceConnection;
  sourceConnectionId: string;
}

export function ConnectSourceAuthCallback({
  onClose,
  onVerified,
  sourceConnection,
  sourceConnectionId,
}: ConnectSourceAuthCallbackProps) {
  const queryClient = useQueryClient();
  const verifyMutationOptions = useVerifySourceConnectionOAuthMutationOptions();
  const sourceConnectionQueryOptions = useGetSourceConnectionQueryOptions({
    sourceConnectionId,
  });
  const claimToken = React.useMemo(
    () => getConnectSourceAuthClaimToken(sourceConnectionId),
    [sourceConnectionId],
  );
  const verifyAttemptRef = React.useRef<string | null>(null);

  const verifyMutation = useMutation({
    ...verifyMutationOptions,
    onSuccess: async (verifiedSourceConnection) => {
      clearConnectSourceAuthClaimToken(sourceConnectionId);
      queryClient.setQueryData(
        sourceConnectionQueryOptions.queryKey,
        verifiedSourceConnection,
      );
      await invalidateSourceConnectionQueries(queryClient);
      await onVerified(verifiedSourceConnection);
    },
  });
  const { mutate: verifyCallback } = verifyMutation;

  React.useEffect(() => {
    if (!claimToken || !sourceConnection.auth.authenticated) {
      return;
    }

    const verifyAttemptKey = `${sourceConnectionId}:${claimToken}`;

    if (verifyAttemptRef.current === verifyAttemptKey) {
      return;
    }

    verifyAttemptRef.current = verifyAttemptKey;

    verifyCallback({
      body: {
        claim_token: claimToken,
      },
      path: {
        source_connection_id: sourceConnectionId,
      },
    });
  }, [
    claimToken,
    sourceConnection.auth.authenticated,
    sourceConnectionId,
    verifyCallback,
  ]);

  if (!sourceConnection.auth.authenticated) {
    return (
      <ConnectSourceAuthError
        backLabel="Close"
        description={
          <p>
            The OAuth callback URL is incomplete or no longer valid for this
            source connection.
            <br />
            Start again from the auth link shown in this step.
          </p>
        }
        hints={[
          'You reopened an old authorization callback link',
          'The provider redirected back after the authorization window expired',
          'The callback URL was opened without the original callback parameters',
        ]}
        onBack={onClose}
        sourceName={sourceConnection.short_name}
        title="Could not resume the OAuth callback"
      />
    );
  }

  if (!claimToken) {
    return (
      <ConnectSourceAuthError
        backLabel="Close"
        description={
          <p>
            Authorization finished, but this browser no longer has the claim
            token needed to finish setup.
            <br />
            Return to the original browser window that started the flow.
          </p>
        }
        hints={[
          'You completed authorization in a different tab or browser',
          'The original browser session was cleared or refreshed',
          'Session storage was unavailable when the callback returned',
        ]}
        onBack={onClose}
        sourceName={sourceConnection.short_name}
        title="Finish setup from the original browser"
      />
    );
  }

  if (verifyMutation.isError) {
    return (
      <ConnectSourceAuthError
        backLabel="Close"
        description={
          <p>
            {getApiErrorMessage(
              verifyMutation.error,
              'Could not verify the OAuth callback.',
            ) ?? 'Could not verify the OAuth callback.'}
          </p>
        }
        hints={[
          'The callback verification token no longer matches this browser session',
          'The authorization window expired before verification completed',
          'The provider authorization was revoked or already consumed',
        ]}
        onBack={onClose}
        sourceName={sourceConnection.short_name}
        title="Could not verify the callback"
      />
    );
  }

  return (
    <ConnectSourceStepLayoutContent className="flex items-center justify-center text-center">
      <Loader />
    </ConnectSourceStepLayoutContent>
  );
}
