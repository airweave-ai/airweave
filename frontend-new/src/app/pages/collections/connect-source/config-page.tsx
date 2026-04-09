import { getRouteApi } from '@tanstack/react-router';
import { useSuspenseQuery } from '@tanstack/react-query';
import { router } from '@/app/router/router';
import {
  SourceConnectionConfigForm,
  isBrowserOAuthMethod,
  useGetSourceQueryOptions,
  useSourceConnectionConfigSubmission,
} from '@/features/source-connections';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';
import {
  FlowDialogAside,
  FlowDialogBody,
  FlowDialogHeader,
  FlowDialogMain,
} from '@/shared/ui/flow-dialog';

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
      <FlowDialogHeader
        onClose={() =>
          void navigate({
            params: { collectionId },
            to: '/collections/$collectionId',
          })
        }
      >
        <div className="min-w-0 space-y-1">
          <DialogTitle className="text-xl font-semibold text-foreground">
            Create Source Connection
          </DialogTitle>
          <DialogDescription className="font-mono text-sm text-muted-foreground">
            Make your {source.name} content searchable for your agent.
          </DialogDescription>
        </div>
      </FlowDialogHeader>

      <FlowDialogBody>
        <FlowDialogMain className="overflow-hidden">
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
        </FlowDialogMain>

        <FlowDialogAside className="xl:w-112">
          <pre className="text-wrap">
            # Initialize the Airweave client client = AirweaveSDK(
            api_key="YOUR_API_KEY", ) # Create connection — returns auth_url for
            OAuth flows response = client.source_connections.create(
            short_name="notion", readable_collection_id="your-collection-id",
            name="Notion Connection", )
          </pre>
        </FlowDialogAside>
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
