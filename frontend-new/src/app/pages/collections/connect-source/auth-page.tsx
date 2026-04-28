import * as React from 'react';
import { useQuery, useSuspenseQueries } from '@tanstack/react-query';
import {
  SearchParamError,
  getRouteApi,
  useRouter,
} from '@tanstack/react-router';
import type { ErrorComponentProps } from '@tanstack/react-router';
import type { SourceConnection } from '@/shared/api';
import {
  ConnectSourceAuthCallback,
  ConnectSourceAuthError,
  ConnectSourceAuthSdkAside,
  ConnectSourceAuthorize,
  ConnectSourceStepDialogHeader,
  ConnectSourceStepLayoutAside,
  ConnectSourceStepLayoutMain,
  SourceConnectionHeader,
  SourceConnectionStepLabel,
  useGetSourceConnectionQueryOptions,
  useGetSourceQueryOptions,
} from '@/features/source-connections';
import { getApiErrorMessage } from '@/shared/api';
import { FlowDialogBody } from '@/shared/ui/flow-dialog';

const routeApi = getRouteApi(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/auth',
);

export function ConnectSourceAuthPage() {
  const navigate = routeApi.useNavigate();
  const router = useRouter();
  const { sourceConnectionId } = routeApi.useLoaderData();
  const { collectionId, source: sourceShortName } = routeApi.useParams();
  const search = routeApi.useSearch();
  const getSourceQueryOptions = useGetSourceQueryOptions({
    sourceShortName,
  });
  const sourceConnectionQueryOptions = useGetSourceConnectionQueryOptions({
    sourceConnectionId,
  });
  const [{ data: source }, { data: sourceConnection }] = useSuspenseQueries({
    queries: [getSourceQueryOptions, sourceConnectionQueryOptions],
  });

  const handleClose = React.useCallback(
    () =>
      void navigate({
        params: { collectionId },
        to: '/collections/$collectionId',
        viewTransition: true,
      }),
    [collectionId, navigate],
  );

  const handleVerified = React.useCallback(
    (verifiedSourceConnection: Pick<SourceConnection, 'id'>) =>
      void navigate({
        params: {
          collectionId,
          source: sourceShortName,
        },
        replace: true,
        search: {
          source_connection_id: verifiedSourceConnection.id,
        },
        to: '/collections/$collectionId/connect-source/$source/sync',
      }),
    [collectionId, navigate, sourceShortName],
  );
  const handleBack = React.useCallback(() => {
    if (router.history.canGoBack()) {
      router.history.back();
      return;
    }

    void navigate({
      params: { collectionId },
      to: '/collections/$collectionId',
      viewTransition: true,
    });
  }, [collectionId, navigate, router]);

  const isCallbackReturn = search.status === 'success';

  return (
    <>
      <ConnectSourceStepDialogHeader
        onClose={handleClose}
        sourceName={source.name}
      />

      <FlowDialogBody>
        <ConnectSourceStepLayoutMain>
          <SourceConnectionHeader
            source={source}
            aside={
              <SourceConnectionStepLabel
                label="Authorize"
                numberOfSteps={2}
                step={2}
              />
            }
          />
          {isCallbackReturn ? (
            <ConnectSourceAuthCallback
              onClose={handleClose}
              onVerified={handleVerified}
              sourceConnection={sourceConnection}
              sourceConnectionId={sourceConnectionId}
            />
          ) : (
            <ConnectSourceAuthorize
              onBack={handleBack}
              sourceConnection={sourceConnection}
              sourceConnectionId={sourceConnectionId}
              sourceName={source.name}
              sourceShortName={source.short_name}
            />
          )}
        </ConnectSourceStepLayoutMain>

        <ConnectSourceStepLayoutAside>
          <ConnectSourceAuthSdkAside sourceName={source.name} />
        </ConnectSourceStepLayoutAside>
      </FlowDialogBody>
    </>
  );
}

export function ConnectSourceAuthErrorPage({ error }: ErrorComponentProps) {
  const navigate = routeApi.useNavigate();
  const router = useRouter();
  const { collectionId, source: sourceShortName } = routeApi.useParams();
  const { source_connection_id: sourceConnectionId } = routeApi.useSearch();
  const sourceQueryOptions = useGetSourceQueryOptions({
    sourceShortName,
  });
  const { data: source } = useQuery(sourceQueryOptions);
  const handleClose = React.useCallback(
    () =>
      void navigate({
        params: { collectionId },
        to: '/collections/$collectionId',
        viewTransition: true,
      }),
    [collectionId, navigate],
  );
  const sourceForLayout = source ?? {
    name: getFallbackSourceName(sourceShortName),
    short_name: sourceShortName,
  };

  const content =
    error instanceof SearchParamError
      ? {
          description:
            'The OAuth callback URL is incomplete or no longer valid for this source connection. Start again from the auth link shown in this step.',
          title: 'Could not resume the OAuth callback',
          hints: [
            'You reopened an old authorization callback link',
            'The provider redirected back after the authorization window expired',
            'The callback URL was opened without the original callback parameters',
          ],
        }
      : {
          description:
            getApiErrorMessage(
              error,
              'Could not load the source connection details.',
            ) ?? 'Could not load the source connection details.',
          title: 'Could not load authorization state',
          hints: [
            'The source connection no longer exists',
            'Your access to this collection changed',
            'The authorization state could not be loaded from the API',
          ],
        };

  return (
    <>
      <ConnectSourceStepDialogHeader
        onClose={handleClose}
        sourceName={sourceForLayout.name}
      />

      <FlowDialogBody>
        <ConnectSourceStepLayoutMain>
          <SourceConnectionHeader
            source={sourceForLayout}
            aside={
              <SourceConnectionStepLabel
                label="Authorize"
                numberOfSteps={2}
                step={2}
              />
            }
          />
          <ConnectSourceAuthError
            backLabel="Close"
            description={<p>{content.description}</p>}
            sourceConnectionId={sourceConnectionId}
            hints={content.hints}
            onBack={handleClose}
            onReauthorized={() => router.invalidate()}
            sourceName={sourceForLayout.name}
            title={content.title}
          />
        </ConnectSourceStepLayoutMain>

        <ConnectSourceStepLayoutAside>
          <ConnectSourceAuthSdkAside sourceName={sourceForLayout.name} />
        </ConnectSourceStepLayoutAside>
      </FlowDialogBody>
    </>
  );
}

function getFallbackSourceName(sourceShortName: string) {
  return sourceShortName
    .split(/[_-]/g)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
}
