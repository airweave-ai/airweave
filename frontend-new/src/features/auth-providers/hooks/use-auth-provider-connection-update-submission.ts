import * as React from 'react';
import { useUpdateAuthProviderConnectionMutation } from '../api';
import type { EditAuthProviderConnectionFormOutput } from '../components/edit-auth-provider-connection-form';
import type {
  AuthProviderConnection,
  AuthProviderConnectionUpdate,
  ConfigValues,
} from '@/shared/api';
import { getApiErrorMessage } from '@/shared/api';

type UseAuthProviderConnectionUpdateSubmissionArgs = {
  connection: AuthProviderConnection;
};

export function useAuthProviderConnectionUpdateSubmission({
  connection,
}: UseAuthProviderConnectionUpdateSubmissionArgs) {
  const updateConnectionMutation = useUpdateAuthProviderConnectionMutation();

  const handleSubmit = React.useCallback(
    async (values: EditAuthProviderConnectionFormOutput) => {
      const body = buildAuthProviderConnectionUpdatePayload({
        currentName: connection.name,
        values,
      });

      if (Object.keys(body).length === 0) {
        return null;
      }

      return updateConnectionMutation.mutateAsync({
        body,
        path: {
          readable_id: connection.readable_id,
        },
      });
    },
    [connection, updateConnectionMutation],
  );

  const submitError = React.useMemo(
    () =>
      getApiErrorMessage(
        updateConnectionMutation.error,
        'Could not update auth provider connection.',
      ),
    [updateConnectionMutation.error],
  );

  return {
    handleSubmit,
    isPending: updateConnectionMutation.isPending,
    reset: updateConnectionMutation.reset,
    submitError,
  };
}

function buildAuthProviderConnectionUpdatePayload({
  currentName,
  values,
}: {
  currentName: string;
  values: EditAuthProviderConnectionFormOutput;
}): AuthProviderConnectionUpdate {
  const body: AuthProviderConnectionUpdate = {};

  if (values.name !== currentName.trim()) {
    body.name = values.name;
  }

  const authFields = removeUndefinedValues(values.auth_fields ?? {}) as ConfigValues;

  if (Object.keys(authFields).length > 0) {
    body.auth_fields = authFields;
  }

  return body;
}

function removeUndefinedValues(value: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(value).filter(([, fieldValue]) => fieldValue !== undefined),
  );
}
