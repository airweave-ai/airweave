import { useMutation } from '@tanstack/react-query';
import { useReinitiateSourceConnectionOAuthMutationOptions } from '../api';
import {
  clearConnectSourceAuthClaimToken,
  setConnectSourceAuthClaimToken,
} from '../components/connect-source-auth/connect-source-auth-storage';

type UseReinitiateSourceConnectionOAuthMutationArgs = {
  errorToast?: false | string;
  sourceConnectionId: string;
};

export function useReinitiateSourceConnectionOAuthMutation({
  errorToast = false,
  sourceConnectionId,
}: UseReinitiateSourceConnectionOAuthMutationArgs) {
  const options = useReinitiateSourceConnectionOAuthMutationOptions();

  return useMutation({
    ...options,
    meta: {
      errorToast,
      ...options.meta,
    },
    onSuccess: (sourceConnection) => {
      const claimToken = sourceConnection.auth.claim_token;

      if (claimToken) {
        setConnectSourceAuthClaimToken(sourceConnectionId, claimToken);
      } else {
        clearConnectSourceAuthClaimToken(sourceConnectionId);
      }
    },
  });
}
