import { getRouteApi } from '@tanstack/react-router';
import { useSuspenseQuery } from '@tanstack/react-query';
import {
  ConnectSourcePrimaryActionButton,
  ConnectSourceStepDialogHeader,
  ConnectSourceStepLayoutActions,
  ConnectSourceStepLayoutAside,
  ConnectSourceStepLayoutContent,
  ConnectSourceStepLayoutMain,
  SourceConnectionHeader,
  useGetSourceQueryOptions,
} from '@/features/source-connections';
import { FlowDialogBody } from '@/shared/ui/flow-dialog';

const routeApi = getRouteApi(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/sync',
);

export function ConnectSourceSyncPage() {
  const navigate = routeApi.useNavigate();
  const { collectionId, source: sourceShortName } = routeApi.useParams();
  const getSourceQueryOptions = useGetSourceQueryOptions({
    sourceShortName,
  });
  const { data: source } = useSuspenseQuery(getSourceQueryOptions);

  const handleClose = () =>
    void navigate({
      params: { collectionId },
      to: '/collections/$collectionId',
    });

  const handleConnectAnotherSource = () =>
    void navigate({
      params: { collectionId },
      to: '/collections/$collectionId/connect-source',
    });

  return (
    <>
      <ConnectSourceStepDialogHeader
        onClose={handleClose}
        sourceName={source.name}
      />

      <FlowDialogBody>
        <ConnectSourceStepLayoutMain>
          <SourceConnectionHeader source={source} />

          <ConnectSourceStepLayoutContent className="flex items-center justify-center text-center">
            <div className="w-full space-y-6 rounded-xl border border-border bg-foreground/5 p-6">
              <div className="space-y-2">
                <p className="text-sm text-foreground">
                  This step is not implemented yet.
                </p>
              </div>
            </div>
          </ConnectSourceStepLayoutContent>

          <ConnectSourceStepLayoutActions
            backLabel="Connect another source"
            onBack={handleConnectAnotherSource}
          >
            <ConnectSourcePrimaryActionButton
              type="button"
              onClick={handleClose}
            >
              Close
            </ConnectSourcePrimaryActionButton>
          </ConnectSourceStepLayoutActions>
        </ConnectSourceStepLayoutMain>

        <ConnectSourceStepLayoutAside>
          <pre className="text-wrap">
            # Initialize the Airweave client client = AirweaveSDK(
            api_key="YOUR_API_KEY", ) # Create connection — returns auth_url for
            OAuth flows response = client.source_connections.create(
            short_name="notion", readable_collection_id="your-collection-id",
            name="Notion Connection", )
          </pre>
        </ConnectSourceStepLayoutAside>
      </FlowDialogBody>
    </>
  );
}
