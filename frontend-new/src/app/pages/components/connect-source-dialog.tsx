import * as React from 'react';
import { X } from 'lucide-react';
import type { ConnectSourceStep } from './connect-source-state';
import { SourcePickerContent } from '@/features/sources';
import { Button } from '@/shared/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/shared/ui/dialog';

interface ConnectSourceDialogProps {
  onClose: () => void;
  onStepChange: (step: ConnectSourceStep) => void;
  step?: ConnectSourceStep;
}

export function ConnectSourceDialog({
  onClose,
  onStepChange,
  step,
}: ConnectSourceDialogProps) {
  const [renderedStep, setRenderedStep] = React.useState(step);

  // `step` is URL-driven, so it becomes `undefined` immediately on close.
  // Keep the last rendered step long enough for Radix to play the exit animation.
  React.useEffect(() => {
    if (step) {
      setRenderedStep(step);
    }
  }, [step]);

  return (
    <Dialog open={Boolean(step)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        showCloseButton={false}
        onAnimationEnd={() => {
          if (!step && renderedStep) {
            setRenderedStep(undefined);
          }
        }}
        className="h-[min(54rem,calc(100vh-1rem))] max-w-[min(84rem,calc(100vw-1rem))] gap-0 overflow-hidden border-border bg-background p-0 text-foreground sm:max-w-[min(84rem,calc(100vw-2rem))]"
      >
        {renderedStep
          ? renderConnectSourceStep({
              onClose,
              onStepChange,
              step: renderedStep,
            })
          : null}
      </DialogContent>
    </Dialog>
  );
}

function renderConnectSourceStep({
  onClose,
  onStepChange,
  step,
}: {
  onClose: () => void;
  onStepChange: (step: ConnectSourceStep) => void;
  step: ConnectSourceStep;
}) {
  switch (step.step) {
    case 'source':
      return (
        <SourcePickerContent
          selectedShortName={undefined}
          onClose={onClose}
          onSelectSource={(source) =>
            onStepChange({
              collectionId: step.collectionId,
              source: source.short_name,
              step: 'config',
            })
          }
        />
      );
    case 'config':
      return (
        <ConnectSourceStepPlaceholder
          title="Configure Connection"
          description="Step state is now driven by the URL. The config UI is next."
          metadata={[
            ['Source', step.source],
            ...(step.collectionId
              ? ([['Collection', step.collectionId]] as const)
              : []),
          ]}
          onClose={onClose}
          onBack={() =>
            onStepChange({
              collectionId: step.collectionId,
              step: 'source',
            })
          }
        />
      );
    case 'auth':
      return (
        <ConnectSourceStepPlaceholder
          title="Authorize Source"
          description="Auth step will restore from URL state once the source-connection flow is built."
          metadata={[
            ['Source', step.source],
            ['Collection', step.collectionId],
            ['Source Connection', step.sourceConnectionId],
          ]}
          onClose={onClose}
        />
      );
    case 'sync':
      return (
        <ConnectSourceStepPlaceholder
          title="Sync Source"
          description="Sync step will resume from URL state once polling/progress UI is built."
          metadata={[
            ['Source', step.source],
            ['Collection', step.collectionId],
            ['Source Connection', step.sourceConnectionId],
          ]}
          onClose={onClose}
        />
      );
  }
}

function ConnectSourceStepPlaceholder({
  description,
  metadata,
  onBack,
  onClose,
  title,
}: {
  description: string;
  metadata: Array<readonly [string, string]>;
  onBack?: () => void;
  onClose: () => void;
  title: string;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center justify-between gap-6 border-b border-border px-6 py-4">
        <div className="min-w-0 space-y-1">
          <DialogTitle className="text-xl font-semibold text-foreground">
            {title}
          </DialogTitle>
          <DialogDescription className="font-mono text-sm text-muted-foreground">
            {description}
          </DialogDescription>
        </div>

        <Button
          type="button"
          variant="outline"
          size="icon"
          className="bg-foreground/5 text-foreground hover:bg-foreground/10"
          onClick={onClose}
        >
          <X className="size-4" />
          <span className="sr-only">Close connect source dialog</span>
        </Button>
      </header>

      <div className="flex flex-1 items-center justify-center px-6 py-8">
        <div className="w-full max-w-md space-y-6 rounded-xl border border-border bg-foreground/5 p-6 text-center">
          <div className="space-y-2">
            <p className="text-sm text-foreground">
              This step is not implemented yet.
            </p>
            <p className="text-sm text-muted-foreground">
              URL state is already preserved, so reload/restore logic can build
              on this.
            </p>
          </div>

          <dl className="space-y-3 text-left">
            {metadata.map(([label, value]) => (
              <div key={label} className="space-y-1">
                <dt className="font-mono text-xs text-muted-foreground uppercase">
                  {label}
                </dt>
                <dd className="text-sm break-all text-foreground">{value}</dd>
              </div>
            ))}
          </dl>

          <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
            {onBack ? (
              <Button type="button" variant="outline" onClick={onBack}>
                Back
              </Button>
            ) : null}
            <Button type="button" variant="ghost" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
