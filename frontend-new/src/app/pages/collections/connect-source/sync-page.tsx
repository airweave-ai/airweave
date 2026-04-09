import { getRouteApi } from '@tanstack/react-router';
import { Button } from '@/shared/ui/button';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';
import {
  FlowDialogAside,
  FlowDialogBody,
  FlowDialogHeader,
  FlowDialogMain,
} from '@/shared/ui/flow-dialog';

const routeApi = getRouteApi(
  '/_authenticated/_app/collections/$collectionId/connect-source/$source/sync',
);

export function ConnectSourceSyncPage() {
  const navigate = routeApi.useNavigate();
  const { collectionId, source } = routeApi.useParams();
  const search = routeApi.useSearch();

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
            Sync Source
          </DialogTitle>
          <DialogDescription className="font-mono text-sm text-muted-foreground">
            Sync step will resume from route state once polling/progress UI is built.
          </DialogDescription>
        </div>
      </FlowDialogHeader>

      <FlowDialogBody>
        <FlowDialogMain className="flex items-center justify-center py-8">
          <div className="w-full max-w-md space-y-6 rounded-xl border border-border bg-foreground/5 p-6 text-center">
            <div className="space-y-2">
              <p className="text-sm text-foreground">
                This step is not implemented yet.
              </p>
              <p className="text-sm text-muted-foreground">
                Route state already preserves collection, source, and source
                connection identity for the next implementation slice.
              </p>
            </div>

            <div className="flex justify-center">
              <Button
                type="button"
                variant="ghost"
                onClick={() =>
                  void navigate({
                    params: { collectionId },
                    to: '/collections/$collectionId',
                  })
                }
              >
                Close
              </Button>
            </div>
          </div>
        </FlowDialogMain>

        <FlowDialogAside className="bg-foreground/[0.02] xl:w-80">
          <div className="space-y-6">
            <div className="space-y-2">
              <p className="text-sm text-foreground">Context</p>
              <p className="text-sm text-muted-foreground">
                The connect-source flow now lives in collection-scoped routes, so
                auth and sync can restore directly from the URL.
              </p>
            </div>

            <dl className="space-y-3 text-left">
              {[
                ['Source', source],
                ['Collection', collectionId],
                ['Source Connection', search.source_connection_id],
              ].map(([label, value]) => (
                <div key={label} className="space-y-1">
                  <dt className="font-mono text-xs text-muted-foreground uppercase">
                    {label}
                  </dt>
                  <dd className="text-sm break-all text-foreground">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </FlowDialogAside>
      </FlowDialogBody>
    </>
  );
}
