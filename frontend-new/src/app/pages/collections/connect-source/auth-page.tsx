import { getRouteApi } from '@tanstack/react-router';
import { useSuspenseQuery } from '@tanstack/react-query';
import {
  ConnectSourceAuth,
  useConnectSourceAuthController,
  useGetSourceQueryOptions,
} from '@/features/source-connections';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';
import {
  FlowDialogAside,
  FlowDialogBody,
  FlowDialogHeader,
  FlowDialogMain,
} from '@/shared/ui/flow-dialog';

const routeApi = getRouteApi(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/auth',
);

export function ConnectSourceAuthPage() {
  const navigate = routeApi.useNavigate();
  const { collectionId, source: sourceShortName } = routeApi.useParams();
  const search = routeApi.useSearch();
  const getSourceQueryOptions = useGetSourceQueryOptions({
    sourceShortName,
  });
  const { data: source } = useSuspenseQuery(getSourceQueryOptions);
  const controller = useConnectSourceAuthController({
    callbackStatus: search.status,
    expectedCollectionId: collectionId,
    expectedSource: sourceShortName,
    onClose: () =>
      void navigate({
        params: { collectionId },
        to: '/collections/$collectionId',
      }),
    onVerified: (sourceConnection) =>
      void navigate({
        params: {
          collectionId,
          source: sourceShortName,
        },
        replace: true,
        search: {
          source_connection_id: sourceConnection.id,
        },
        to: '/collections/$collectionId/connect-source/$source/sync',
      }),
    sourceConnectionId: search.source_connection_id,
  });

  return (
    <>
      <FlowDialogHeader onClose={controller.close}>
        <div className="min-w-0 space-y-1">
          <p className="font-mono text-xs tracking-[0.18em] text-muted-foreground uppercase">
            Step 2 of 2: Authorize
          </p>
          <DialogTitle className="text-xl font-semibold text-foreground">
            Authorize {source.name}
          </DialogTitle>
          <DialogDescription className="font-mono text-sm text-muted-foreground">
            Finish the browser OAuth flow, then Airweave will verify this window
            and continue setup.
          </DialogDescription>
        </div>
      </FlowDialogHeader>

      <FlowDialogBody>
        <FlowDialogMain className="flex items-center justify-center">
          <div className="w-full max-w-2xl py-8">
            <ConnectSourceAuth
              onClose={controller.close}
              onConnectNow={controller.connectNow}
              onReauthorize={controller.reauthorize}
              sourceName={source.name}
              state={controller.state}
            />
          </div>
        </FlowDialogMain>

        <FlowDialogAside className="bg-foreground/[0.02] xl:w-96">
          <div className="space-y-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">
                What happens next
              </p>
              <p className="text-sm text-muted-foreground">
                OAuth finishes in two steps: the provider authorizes access,
                then Airweave verifies the original browser session and starts
                the sync flow.
              </p>
            </div>

            <div className="space-y-4 text-sm text-muted-foreground">
              <div className="space-y-1">
                <p className="text-foreground">Keep this window open</p>
                <p>
                  The copied link can finish provider auth, but this browser
                  still needs to complete the Airweave verification step.
                </p>
              </div>

              <div className="space-y-1">
                <p className="text-foreground">Auth links can expire</p>
                <p>
                  If the authorization URL is already consumed or missing, use a
                  fresh re-authorization link from this screen.
                </p>
              </div>

              <div className="space-y-1">
                <p className="text-foreground">Callback resumes setup</p>
                <p>
                  After provider auth, Airweave returns to this auth route,
                  verifies the initiating session, then continues into sync.
                </p>
              </div>
            </div>
          </div>
        </FlowDialogAside>
      </FlowDialogBody>
    </>
  );
}
