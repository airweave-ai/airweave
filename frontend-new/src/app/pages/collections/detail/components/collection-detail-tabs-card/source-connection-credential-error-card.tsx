import { Link, useNavigate } from '@tanstack/react-router';
import {
  IconAlertTriangleFilled,
  IconExternalLink,
  IconRefresh,
} from '@tabler/icons-react';
import type * as React from 'react';
import type {
  SourceConnection,
  SourceConnectionErrorCategory,
} from '@/shared/api';
import { useReinitiateSourceConnectionOAuthMutation } from '@/features/source-connections';
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert';
import { Button } from '@/shared/ui/button';

type SourceConnectionCredentialErrorCardProps = {
  sourceConnection: CredentialErrorSourceConnection;
};

type CredentialErrorSourceConnection = Pick<
  SourceConnection,
  | 'error_category'
  | 'error_message'
  | 'id'
  | 'provider_settings_url'
  | 'provider_short_name'
  | 'readable_collection_id'
  | 'short_name'
>;

type CredentialErrorConfig = {
  actions?: React.ComponentType<SourceConnectionCredentialErrorCardProps>;
  title: string;
  description: string;
};

const credentialErrorConfig: Partial<
  Record<SourceConnectionErrorCategory, CredentialErrorConfig>
> = {
  oauth_credentials_expired: {
    actions: OAuthCredentialsExpiredActions,
    title: 'Re-authorization required',
    description:
      'Your OAuth authorization has expired or been revoked. Re-authorize to restore the connection.',
  },
  api_key_invalid: {
    // TODO: add recovery for invalid API key error category
    title: 'API key invalid',
    description:
      'The API key for this connection is no longer valid. Update credentials to restore syncing.',
  },
  auth_provider_account_gone: {
    actions: AuthProviderCredentialErrorActions,
    title: 'Auth provider account not found',
    description:
      'The connected account on the auth provider has been deleted or deactivated. Check your provider dashboard.',
  },
  auth_provider_credentials_invalid: {
    actions: AuthProviderCredentialErrorActions,
    title: 'Auth provider credentials invalid',
    description:
      'The credentials on the auth provider need to be refreshed or reconfigured.',
  },
};

export function SourceConnectionCredentialErrorCard({
  sourceConnection,
}: SourceConnectionCredentialErrorCardProps) {
  const errorCategory = sourceConnection.error_category;
  const config = errorCategory ? credentialErrorConfig[errorCategory] : null;

  if (!config) {
    return null;
  }

  const Actions = config.actions;

  return (
    <Alert variant="destructive">
      <IconAlertTriangleFilled />
      <AlertTitle>{config.title}</AlertTitle>
      <AlertDescription>
        {sourceConnection.error_message ?? config.description}
      </AlertDescription>

      {Actions ? (
        <div className="col-start-2 mt-3 flex flex-wrap gap-2">
          <Actions sourceConnection={sourceConnection} />
        </div>
      ) : null}
    </Alert>
  );
}

function OAuthCredentialsExpiredActions({
  sourceConnection,
}: SourceConnectionCredentialErrorCardProps) {
  const navigate = useNavigate();
  const reauthorizeMutation = useReinitiateSourceConnectionOAuthMutation({
    errorToast: 'Could not create a fresh authorization link.',
    sourceConnectionId: sourceConnection.id,
  });

  return (
    <Button
      size="sm"
      variant="outline"
      className="text-foreground"
      disabled={reauthorizeMutation.isPending}
      onClick={() =>
        reauthorizeMutation.mutate(
          {
            path: {
              source_connection_id: sourceConnection.id,
            },
          },
          {
            onSuccess: () =>
              void navigate({
                params: {
                  collectionId: sourceConnection.readable_collection_id,
                  source: sourceConnection.short_name,
                },
                search: {
                  source_connection_id: sourceConnection.id,
                },
                to: '/collections/$collectionId/connect-source/$source/auth',
              }),
          },
        )
      }
    >
      <IconRefresh className="size-3.5" />
      Re-authorize
    </Button>
  );
}

function AuthProviderCredentialErrorActions({
  sourceConnection,
}: {
  sourceConnection: CredentialErrorSourceConnection;
}) {
  return (
    <>
      {sourceConnection.provider_settings_url ? (
        <Button asChild size="sm" variant="outline" className="text-foreground">
          <a
            href={sourceConnection.provider_settings_url}
            rel="noopener noreferrer"
            target="_blank"
          >
            <IconExternalLink className="size-3.5" />
            Open provider dashboard
          </a>
        </Button>
      ) : null}
      <Button asChild size="sm" variant="outline" className="text-foreground">
        <Link to="/auth-providers">
          <IconAlertTriangleFilled className="size-3.5" />
          Auth providers settings
        </Link>
      </Button>
    </>
  );
}
