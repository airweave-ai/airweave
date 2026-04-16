import { useSuspenseQueries } from '@tanstack/react-query';
import { getRouteApi } from '@tanstack/react-router';
import {
  ConnectSourceStepDialogHeader,
  ConnectSourceStepLayoutAside,
  ConnectSourceStepLayoutMain,
  ConnectSourceSync,
  ConnectSourceSyncSdkAside,
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
            viewTransition: true,
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
                viewTransition: true,
              })
            }
            source={source}
            sourceConnection={sourceConnection}
          />
        </ConnectSourceStepLayoutMain>

        <ConnectSourceStepLayoutAside>
          <ConnectSourceSyncSdkAside sourceName={source.name} />
        </ConnectSourceStepLayoutAside>
      </FlowDialogBody>
    </>
  );
}
