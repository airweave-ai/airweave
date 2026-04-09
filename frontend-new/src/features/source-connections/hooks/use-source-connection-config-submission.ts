import * as React from 'react';
import { useCreateSourceConnectionMutation } from '../api';
import { setConnectSourceAuthClaimToken } from '../components/connect-source-auth/connect-source-auth-storage';
import { getAuthMethodForVariant } from '../components/source-connection-config-form/source-connection-form-hook';
import type { SourceConnectionFormOutput } from '../components/source-connection-config-form';
import type {
  Source,
  SourceConnectionCreate,
} from '@/shared/api';
import { getApiErrorMessage } from '@/shared/api';

interface UseSourceConnectionConfigSubmissionArgs {
  collectionId: string;
  redirectUrl: string;
  source: Source;
}

export function useSourceConnectionConfigSubmission({
  collectionId,
  redirectUrl,
  source,
}: UseSourceConnectionConfigSubmissionArgs) {
  const createSourceConnectionMutation = useCreateSourceConnectionMutation();

  const handleSubmit = React.useCallback(
    async (values: SourceConnectionFormOutput) => {
      const sourceConnection = await createSourceConnectionMutation.mutateAsync({
        body: buildSourceConnectionPayload({
          redirectUrl,
          readableCollectionId: collectionId,
          source,
          values,
        }),
      });

      if (sourceConnection.auth.claim_token) {
        setConnectSourceAuthClaimToken(
          sourceConnection.id,
          sourceConnection.auth.claim_token,
        );
      }

      return sourceConnection;
    },
    [collectionId, createSourceConnectionMutation, redirectUrl, source],
  );

  const submitError = React.useMemo(
    () =>
      getApiErrorMessage(
        createSourceConnectionMutation.error,
        'Could not create source connection.',
      ),
    [createSourceConnectionMutation.error],
  );

  return {
    handleSubmit,
    isPending: createSourceConnectionMutation.isPending,
    submitError,
  };
}

function buildSourceConnectionPayload({
  redirectUrl,
  readableCollectionId,
  source,
  values,
}: {
  redirectUrl: string;
  readableCollectionId: string;
  source: Source;
  values: SourceConnectionFormOutput;
}): SourceConnectionCreate {
  const authMethod = getAuthMethodForVariant(values.authVariant);
  const syncImmediately = authMethod !== 'oauth_browser';

  return {
    authentication: values.authentication,
    config: values.config,
    name: values.name,
    readable_collection_id: readableCollectionId,
    redirect_url: authMethod === 'oauth_browser' ? redirectUrl : undefined,
    short_name: source.short_name,
    sync_immediately: source.supports_browse_tree ? false : syncImmediately,
  };
}
