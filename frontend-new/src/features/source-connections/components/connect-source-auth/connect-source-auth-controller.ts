import * as React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getSourceConnectionQueryOptions,
  invalidateSourceConnectionQueries,
  useReinitiateSourceConnectionOAuthMutationOptions,
  useVerifySourceConnectionOAuthMutationOptions,
} from '../../api';
import {
  deriveConnectSourceAuthState,
  shouldAutoVerifyConnectSourceAuthReturn,
} from './connect-source-auth-state';
import {
  clearConnectSourceAuthClaimToken,
  getConnectSourceAuthClaimToken,
  setConnectSourceAuthClaimToken,
} from './connect-source-auth-storage';
import type { ConnectSourceAuthState } from './connect-source-auth-state';
import type { SourceConnection } from '@/shared/api';
import { getApiErrorMessage } from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

interface UseConnectSourceAuthControllerArgs {
  callbackStatus?: string;
  expectedCollectionId: string;
  expectedSource: string;
  onClose: () => void;
  onVerified: (sourceConnection: SourceConnection) => Promise<void> | void;
  sourceConnectionId?: string;
}

interface ConnectSourceAuthController {
  close: () => void;
  connectNow: () => void;
  reauthorize: () => Promise<void>;
  sourceConnection: SourceConnection | null;
  state: ConnectSourceAuthState;
}

export function useConnectSourceAuthController({
  callbackStatus,
  expectedCollectionId,
  expectedSource,
  onClose,
  onVerified,
  sourceConnectionId,
}: UseConnectSourceAuthControllerArgs): ConnectSourceAuthController {
  const queryClient = useQueryClient();
  const organizationId = useCurrentOrganizationId();
  const reauthorizeMutationOptions =
    useReinitiateSourceConnectionOAuthMutationOptions();
  const verifyMutationOptions = useVerifySourceConnectionOAuthMutationOptions();

  const sourceConnectionQueryOptions = React.useMemo(
    () =>
      sourceConnectionId
        ? getSourceConnectionQueryOptions(organizationId, {
            sourceConnectionId,
          })
        : null,
    [organizationId, sourceConnectionId],
  );

  const sourceConnectionQuery = useQuery({
    ...(sourceConnectionQueryOptions ?? {
      queryFn: () => null,
      queryKey: ['connect-source-auth', 'missing-source-connection-id'],
    }),
    enabled: sourceConnectionQueryOptions != null,
  });

  const verifyMutation = useMutation({
    ...verifyMutationOptions,
    onSuccess: async (verifiedSourceConnection) => {
      if (sourceConnectionId && sourceConnectionQueryOptions) {
        clearConnectSourceAuthClaimToken(sourceConnectionId);
        queryClient.setQueryData(
          sourceConnectionQueryOptions.queryKey,
          verifiedSourceConnection,
        );
        await invalidateSourceConnectionQueries(queryClient);
      }

      await onVerified(verifiedSourceConnection);
    },
  });

  const reauthorizeMutation = useMutation({
    ...reauthorizeMutationOptions,
    onSuccess: async (nextSourceConnection) => {
      if (!sourceConnectionId || !sourceConnectionQueryOptions) {
        return;
      }

      const nextClaimToken = nextSourceConnection.auth.claim_token;

      if (nextClaimToken) {
        setConnectSourceAuthClaimToken(sourceConnectionId, nextClaimToken);
      } else {
        clearConnectSourceAuthClaimToken(sourceConnectionId);
      }

      queryClient.setQueryData(
        sourceConnectionQueryOptions.queryKey,
        nextSourceConnection,
      );
      await invalidateSourceConnectionQueries(queryClient);
    },
  });

  const claimToken = React.useMemo(
    () =>
      sourceConnectionId
        ? getConnectSourceAuthClaimToken(sourceConnectionId)
        : null,
    [sourceConnectionId, sourceConnectionQuery.dataUpdatedAt],
  );

  const sourceConnection = sourceConnectionQuery.data;
  const state = React.useMemo(
    () =>
      deriveConnectSourceAuthState({
        callbackStatus,
        claimToken,
        expectedCollectionId,
        expectedSource,
        isConnectionLoading: sourceConnectionQuery.isLoading,
        reauthorizeErrorMessage: getErrorMessage(
          reauthorizeMutation.error,
          'Could not create a fresh authorization link.',
        ),
        reauthorizeStatus: reauthorizeMutation.status,
        sourceConnection,
        sourceConnectionErrorMessage: getErrorMessage(
          sourceConnectionQuery.error,
          'Could not load the source connection details.',
        ),
        sourceConnectionId,
        verifyErrorMessage: getErrorMessage(
          verifyMutation.error,
          'Could not verify the OAuth callback.',
        ),
        verifyStatus: verifyMutation.status,
      }),
    [
      callbackStatus,
      claimToken,
      expectedCollectionId,
      expectedSource,
      reauthorizeMutation.error,
      reauthorizeMutation.status,
      sourceConnection,
      sourceConnectionId,
      sourceConnectionQuery.error,
      sourceConnectionQuery.isLoading,
      verifyMutation.error,
      verifyMutation.status,
    ],
  );

  const shouldAutoVerify = React.useMemo(
    () =>
      shouldAutoVerifyConnectSourceAuthReturn({
        callbackStatus,
        claimToken,
        sourceConnection,
        sourceConnectionId,
        verifyStatus: verifyMutation.status,
      }),
    [
      callbackStatus,
      claimToken,
      sourceConnection,
      sourceConnectionId,
      verifyMutation.status,
    ],
  );

  React.useEffect(() => {
    if (!shouldAutoVerify || !claimToken || !sourceConnectionId) {
      return;
    }

    verifyMutation.mutate({
      body: {
        claim_token: claimToken,
      },
      path: {
        source_connection_id: sourceConnectionId,
      },
    });
  }, [claimToken, shouldAutoVerify, sourceConnectionId, verifyMutation]);

  const connectNow = React.useCallback(() => {
    if (state.kind !== 'authorize-ready') {
      return;
    }

    window.location.assign(state.authUrl);
  }, [state]);

  const reauthorize = React.useCallback(async () => {
    if (!sourceConnectionId || reauthorizeMutation.isPending) {
      return;
    }

    await reauthorizeMutation.mutateAsync({
      path: {
        source_connection_id: sourceConnectionId,
      },
    });
  }, [reauthorizeMutation, sourceConnectionId]);

  return {
    close: onClose,
    connectNow,
    reauthorize,
    sourceConnection,
    state,
  };
}

function getErrorMessage(error: unknown, fallbackMessage: string) {
  return getApiErrorMessage(error, fallbackMessage);
}
