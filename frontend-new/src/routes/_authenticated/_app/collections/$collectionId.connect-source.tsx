import * as React from 'react';
import { Outlet, createFileRoute } from '@tanstack/react-router';
import { AirweaveLoader } from '@/shared/components/airweave-loader';
import { FlowDialog, FlowDialogContent } from '@/shared/components/flow-dialog';

export const Route = createFileRoute(
  '/_authenticated/_app/collections/$collectionId/connect-source',
)({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = Route.useNavigate();
  const { collectionId } = Route.useParams();
  const handleClose = React.useCallback(
    () =>
      void navigate({
        params: { collectionId },
        to: '/collections/$collectionId',
        viewTransition: true,
      }),
    [collectionId, navigate],
  );

  return (
    <FlowDialog open onOpenChange={(nextOpen) => !nextOpen && handleClose()}>
      <FlowDialogContent>
        <React.Suspense
          fallback={<AirweaveLoader className="row-span-2 min-h-0" />}
        >
          <Outlet />
        </React.Suspense>
      </FlowDialogContent>
    </FlowDialog>
  );
}
