import { useSuspenseQueries } from '@tanstack/react-query';
import { getRouteApi } from '@tanstack/react-router';
import {
  ConnectSourceStepDialogHeader,
  ConnectSourceStepLayoutAside,
  ConnectSourceStepLayoutMain,
  ConnectSourceSync,
  useGetSourceConnectionQueryOptions,
  useGetSourceQueryOptions,
} from '@/features/source-connections';
import { FlowDialogBody } from '@/shared/ui/flow-dialog';

const routeApi = getRouteApi(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/sync',
);

export function ConnectSourceSyncPage() {
  const navigate = routeApi.useNavigate();
  const { collectionId, source: sourceShortName } = routeApi.useParams();
  const { sourceConnectionId } = routeApi.useLoaderData();
  const sourceQueryOptions = useGetSourceQueryOptions({
    sourceShortName,
  });
  const sourceConnectionQueryOptions = useGetSourceConnectionQueryOptions({
    sourceConnectionId,
  });
  const [{ data: source }, { data: sourceConnection }] = useSuspenseQueries({
    queries: [sourceQueryOptions, sourceConnectionQueryOptions],
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
          <ConnectSourceSync
            lastJob={sourceConnection.sync?.last_job ?? null}
            onBack={() =>
              void navigate({
                params: { collectionId },
                to: '/collections/$collectionId/connect-source',
              })
            }
            onClose={() =>
              void navigate({
                params: { collectionId },
                to: '/collections/$collectionId',
              })
            }
            source={source}
            sourceConnection={sourceConnection}
          />
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
