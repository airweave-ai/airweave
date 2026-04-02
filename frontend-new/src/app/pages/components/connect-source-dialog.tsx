import * as React from 'react';
import type { ConnectSourceStep } from './connect-source-state';
import type { Source } from '@/shared/api';
import {
  SourcePickerFilters,
  SourcePickerResults,
  useSourcePicker,
} from '@/features/sources';
import { Button } from '@/shared/ui/button';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';
import {
  FlowDialog,
  FlowDialogAside,
  FlowDialogBody,
  FlowDialogContent,
  FlowDialogHeader,
  FlowDialogMain,
} from '@/shared/ui/flow-dialog';

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
    <FlowDialog
      open={Boolean(step)}
      onOpenChange={(open) => !open && onClose()}
    >
      <FlowDialogContent
        onAnimationEnd={() => {
          if (!step && renderedStep) {
            setRenderedStep(undefined);
          }
        }}
      >
        {renderedStep
          ? renderConnectSourceStep({
              onClose,
              onStepChange,
              step: renderedStep,
            })
          : null}
      </FlowDialogContent>
    </FlowDialog>
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
        <ConnectSourcePickerStep
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

function ConnectSourcePickerStep({
  onClose,
  onSelectSource,
}: {
  onClose: () => void;
  onSelectSource?: (source: Source) => void;
}) {
  const {
    activeLabel,
    clearFilters,
    error,
    filteredSourceCount,
    filteredSources,
    hasFilters,
    isLoading,
    labelCounts,
    refetch,
    search,
    setActiveLabel,
    setSearch,
    totalSourceCount,
  } = useSourcePicker();

  return (
    <>
      <FlowDialogHeader onClose={onClose}>
        <div className="min-w-0 space-y-1">
          <DialogTitle className="text-xl font-semibold text-foreground">
            Select Source
          </DialogTitle>
          <DialogDescription className="font-mono text-sm text-muted-foreground">
            Make your content searchable for your agent.
          </DialogDescription>
        </div>
      </FlowDialogHeader>

      <FlowDialogBody>
        <FlowDialogAside className="xl:w-110">
          <SourcePickerFilters
            activeLabel={activeLabel}
            filteredSourceCount={filteredSourceCount}
            isLoading={isLoading}
            labelCounts={labelCounts}
            onActiveLabelChange={setActiveLabel}
            onSearchChange={setSearch}
            search={search}
            totalSourceCount={totalSourceCount}
          />
        </FlowDialogAside>

        <FlowDialogMain>
          <SourcePickerResults
            error={error}
            filteredSources={filteredSources}
            hasFilters={hasFilters}
            isLoading={isLoading}
            onClearFilters={clearFilters}
            onRetry={() => void refetch()}
            onSelectSource={onSelectSource}
          />
        </FlowDialogMain>
      </FlowDialogBody>
    </>
  );
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
    <>
      <FlowDialogHeader onClose={onClose}>
        <div className="min-w-0 space-y-1">
          <DialogTitle className="text-xl font-semibold text-foreground">
            {title}
          </DialogTitle>
          <DialogDescription className="font-mono text-sm text-muted-foreground">
            {description}
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
                URL state is already preserved, so reload/restore logic can
                build on this.
              </p>
            </div>

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
        </FlowDialogMain>

        <FlowDialogAside className="bg-foreground/[0.02] xl:w-80">
          <div className="space-y-6">
            <div className="space-y-2">
              <p className="text-sm text-foreground">Context</p>
              <p className="text-sm text-muted-foreground">
                Current URL state is available already, so config, auth, and
                sync can restore cleanly after reload.
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
          </div>
        </FlowDialogAside>
      </FlowDialogBody>
    </>
  );
}
