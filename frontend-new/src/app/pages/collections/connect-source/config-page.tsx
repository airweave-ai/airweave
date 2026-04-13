import { getRouteApi } from '@tanstack/react-router';
import { useSuspenseQuery } from '@tanstack/react-query';
import { router } from '@/app/router/router';
import {
  ConnectSourceConfigSdkAside,
  ConnectSourceStepDialogHeader,
  ConnectSourceStepLayoutAside,
  ConnectSourceStepLayoutMain,
  SourceConnectionConfigForm,
  isBrowserOAuthMethod,
  useGetSourceQueryOptions,
  useSourceConnectionConfigSubmission,
} from '@/features/source-connections';
import { FlowDialogBody } from '@/shared/ui/flow-dialog';

const routeApi = getRouteApi(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/config',
);

export function ConnectSourceConfigPage() {
  const navigate = routeApi.useNavigate();
  const { collectionId, source: sourceShortName } = routeApi.useParams();
  const getSourceQueryOptions = useGetSourceQueryOptions({
    sourceShortName,
  });
  const { data: source } = useSuspenseQuery(getSourceQueryOptions);
  const { handleSubmit, submitError } = useSourceConnectionConfigSubmission({
    collectionId,
    redirectUrl: buildConnectSourceAuthRedirectUrl({
      collectionId,
      sourceShortName: source.short_name,
    }),
    source,
  });

  return (
    <>
      <ConnectSourceStepDialogHeader
        onClose={() =>
          void navigate({
            params: { collectionId },
            to: '/collections/$collectionId',
          })
        }
        sourceName={source.name}
      />

      <FlowDialogBody>
        <ConnectSourceStepLayoutMain>
          <SourceConnectionConfigForm
            onBack={() =>
              void navigate({
                params: { collectionId },
                to: '/collections/$collectionId/connect-source',
              })
            }
            onSubmit={async (values) => {
              const sourceConnection = await handleSubmit(values);
              await navigate({
                params: {
                  collectionId,
                  source: sourceShortName,
                },
                replace: true,
                search: {
                  source_connection_id: sourceConnection.id,
                },
                to: isBrowserOAuthMethod(sourceConnection.auth.method)
                  ? '/collections/$collectionId/connect-source/$source/auth'
                  : '/collections/$collectionId/connect-source/$source/sync',
              });
            }}
            source={source}
            submitError={submitError}
          />
        </ConnectSourceStepLayoutMain>

        <ConnectSourceStepLayoutAside>
          <ConnectSourceConfigSdkAside sourceName={source.name} />
        </ConnectSourceStepLayoutAside>
      </FlowDialogBody>
    </>
  );
}

function buildConnectSourceAuthRedirectUrl({
  collectionId,
  sourceShortName,
}: {
  collectionId: string;
  sourceShortName: string;
}) {
  const location = router.buildLocation({
    params: {
      collectionId,
      source: sourceShortName,
    },
    to: '/collections/$collectionId/connect-source/$source/auth',
  });

  return new URL(location.href, window.location.origin).toString();
}
