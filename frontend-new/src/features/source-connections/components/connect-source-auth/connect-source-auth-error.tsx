import * as React from 'react';
import { IconExclamationCircle, IconRefresh } from '@tabler/icons-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  invalidateSourceConnectionQueries,
  useGetSourceConnectionQueryOptions,
  useReinitiateSourceConnectionOAuthMutationOptions,
} from '../../api';
import {
  ConnectSourcePrimaryActionButton,
  ConnectSourceStepLayoutActions,
  ConnectSourceStepLayoutContent,
} from '../connect-source-step-layout';
import {
  clearConnectSourceAuthClaimToken,
  setConnectSourceAuthClaimToken,
} from './connect-source-auth-storage';
import { getApiErrorMessage } from '@/shared/api';
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert';
import { FieldError } from '@/shared/ui/field';
import { Separator } from '@/shared/ui/separator';

interface ConnectSourceAuthErrorProps {
  backLabel?: string;
  description: React.ReactNode;
  hints: Array<string>;
  onBack: () => void;
  sourceConnectionId?: string;
  sourceName: string;
  title: string;
}

export function ConnectSourceAuthError({
  backLabel,
  description,
  hints,
  onBack,
  sourceConnectionId,
  sourceName,
  title,
}: ConnectSourceAuthErrorProps) {
  return (
    <>
      <ConnectSourceStepLayoutContent>
        <Alert
          variant="destructive"
          className="gap-3 gap-y-1 rounded-lg border-border p-3"
        >
          <IconExclamationCircle className="size-4" />
          <AlertTitle>{title}</AlertTitle>
          <AlertDescription className="space-y-3 font-mono text-sm leading-5">
            <div className="text-destructive-foreground">{description}</div>

            <Separator />

            <div className="space-y-1">
              <span className="font-sans text-sm font-semibold text-destructive">
                What likely happened:
              </span>
              <ul className="ml-5 list-disc space-y-0.5 text-destructive-foreground">
                {hints.map((hint) => (
                  <li key={hint}>{hint}</li>
                ))}
              </ul>
            </div>
          </AlertDescription>
        </Alert>
      </ConnectSourceStepLayoutContent>

      {sourceConnectionId ? (
        <ReconnectActions
          backLabel={backLabel}
          onBack={onBack}
          sourceConnectionId={sourceConnectionId}
          sourceName={sourceName}
        />
      ) : (
        <ConnectSourceStepLayoutActions backLabel={backLabel} onBack={onBack} />
      )}
    </>
  );
}

function ReconnectActions({
  backLabel,
  onBack,
  sourceConnectionId,
  sourceName,
}: {
  backLabel?: string;
  onBack: () => void;
  sourceConnectionId: string;
  sourceName: string;
}) {
  const queryClient = useQueryClient();
  const reauthorizeMutationOptions =
    useReinitiateSourceConnectionOAuthMutationOptions();
  const sourceConnectionQueryOptions = useGetSourceConnectionQueryOptions({
    sourceConnectionId,
  });

  const reauthorizeMutation = useMutation({
    ...reauthorizeMutationOptions,
    onSuccess: async (nextSourceConnection) => {
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

  const reauthorizeErrorMessage = getApiErrorMessage(
    reauthorizeMutation.error,
    'Could not create a fresh authorization link.',
  );

  return (
    <div className="shrink-0 space-y-2">
      {reauthorizeErrorMessage ? (
        <FieldError>{reauthorizeErrorMessage}</FieldError>
      ) : null}

      <ConnectSourceStepLayoutActions
        backLabel={backLabel}
        onBack={onBack}
        backDisabled={reauthorizeMutation.isPending}
      >
        <ConnectSourcePrimaryActionButton
          type="button"
          onClick={() =>
            void reauthorizeMutation.mutateAsync({
              path: {
                source_connection_id: sourceConnectionId,
              },
            })
          }
          icon={<IconRefresh className="size-4" />}
          isLoading={reauthorizeMutation.isPending}
        >
          Re-authorize {sourceName}
        </ConnectSourcePrimaryActionButton>
      </ConnectSourceStepLayoutActions>
    </div>
  );
}
