import { useSuspenseQuery } from '@tanstack/react-query';
import {
  useCreateSourceConnectionMutation,
  useGetSourceQueryOptions,
} from '../../api';
import { useSourcePicker } from '../../hooks/use-source-picker';
import { SourceIcon } from '../source-icon';
import { SourcePickerFilters } from '../source-picker-filters';
import { SourcePickerResults } from '../source-picker-results';
import { SourceConnectionForm } from './source-connection-form';
import type { ConnectSourceStep } from './connect-source-state';
import type { SourceConnectionFormValues } from '../../types';
import type {
  DirectAuthentication,
  Source,
  SourceConnectionCreate,
} from '@/shared/api';
import { Button } from '@/shared/ui/button';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';
import {
  FlowDialogAside,
  FlowDialogBody,
  FlowDialogHeader,
  FlowDialogMain,
} from '@/shared/ui/flow-dialog';

interface ConnectSourceDialogScreenProps {
  onClose: () => void;
  onStepChange: (step: ConnectSourceStep) => void;
  step: ConnectSourceStep;
}

export function ConnectSourceDialogScreen({
  onClose,
  onStepChange,
  step,
}: ConnectSourceDialogScreenProps) {
  return (
    <ConnectSourceStep
      onClose={onClose}
      onStepChange={onStepChange}
      step={step}
    />
  );
}

function ConnectSourceStep({
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
        <ConnectSourceConfigStep
          collectionId={step.collectionId}
          onClose={onClose}
          onBack={() =>
            onStepChange({
              collectionId: step.collectionId,
              step: 'source',
            })
          }
          onStepChange={onStepChange}
          source={step.source}
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

function ConnectSourceConfigStep({
  collectionId,
  onBack,
  onClose,
  onStepChange,
  source: sourceShortName,
}: {
  collectionId: string;
  onBack: () => void;
  onClose: () => void;
  onStepChange: (step: ConnectSourceStep) => void;
  source: string;
}) {
  const getSourceQueryOptions = useGetSourceQueryOptions({
    sourceShortName: sourceShortName,
  });
  const { data: source } = useSuspenseQuery(getSourceQueryOptions);
  const createSourceConnectionMutation = useCreateSourceConnectionMutation();

  const isPending = createSourceConnectionMutation.isPending;

  const handleSubmit = async (values: SourceConnectionFormValues) => {
    const sourceConnection = await createSourceConnectionMutation.mutateAsync({
      body: buildSourceConnectionPayload({
        authMethod: values.authMethod,
        readableCollectionId: collectionId,
        source,
        values,
      }),
    });

    onStepChange({
      collectionId: sourceConnection.readable_collection_id,
      source: sourceShortName,
      sourceConnectionId: sourceConnection.id,
      step: resolveNextConnectSourceStep({
        authMethod: values.authMethod,
        source,
      }),
    });
  };

  return (
    <>
      <FlowDialogHeader onClose={onClose}>
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
        <FlowDialogMain className="space-y-6">
          <div className="flex justify-between gap-3">
            <div className="flex gap-3">
              <div className="flex size-10 items-center justify-center rounded-xs border bg-muted">
                <SourceIcon
                  className="size-4"
                  name={source.name}
                  shortName={source.short_name}
                />
              </div>
              <div>
                <h2 className="font-medium">Connect {source.name}</h2>
                <a className="font-mono text-sm font-normal text-muted-foreground">
                  See Docs
                </a>
              </div>
            </div>
          </div>
          <SourceConnectionForm
            footerStart={
              <>
                <Button
                  type="button"
                  variant="outline"
                  onClick={onBack}
                  disabled={isPending}
                >
                  Back
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={onClose}
                  disabled={isPending}
                >
                  Cancel
                </Button>
              </>
            }
            isSubmitting={isPending}
            onSubmit={handleSubmit}
            source={source}
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

function resolveNextConnectSourceStep({
  authMethod,
  source,
}: {
  authMethod: SourceConnectionFormValues['authMethod'];
  source: Source;
}) {
  return getSyncImmediately({ authMethod, source }) ? 'sync' : 'auth';
}

function getSyncImmediately({
  authMethod,
  source,
}: {
  authMethod: SourceConnectionFormValues['authMethod'];
  source: Source;
}) {
  if (source.supports_browse_tree) {
    return false;
  }

  return authMethod !== 'oauth_browser';
}

function buildSourceConnectionPayload({
  authMethod,
  readableCollectionId,
  source,
  values,
}: {
  authMethod: SourceConnectionFormValues['authMethod'];
  readableCollectionId: string;
  source: Source;
  values: SourceConnectionFormValues;
}): SourceConnectionCreate {
  const syncImmediately = getSyncImmediately({ authMethod, source });

  return {
    authentication:
      authMethod === 'direct'
        ? buildDirectAuthentication(values.authentication.credentials ?? {})
        : null,
    config: trimEmptyValues(values.config),
    name: trimFormString(values.name),
    readable_collection_id: readableCollectionId,
    short_name: source.short_name,
    sync_immediately: syncImmediately,
  };
}

function buildDirectAuthentication(
  credentials: Record<string, unknown>,
): DirectAuthentication {
  return {
    credentials: trimEmptyValues(credentials),
  };
}

function trimFormString(value: string) {
  const trimmedValue = value.trim();

  return trimmedValue.length > 0 ? trimmedValue : undefined;
}

function trimEmptyValues(values: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(values).flatMap(([key, value]) => {
      if (value === null || value === undefined) {
        return [];
      }

      if (typeof value === 'string') {
        const trimmedValue = value.trim();
        return trimmedValue.length > 0 ? [[key, trimmedValue]] : [];
      }

      if (Array.isArray(value)) {
        const nextValue = value
          .map((item) => (typeof item === 'string' ? item.trim() : item))
          .filter((item) => item !== '' && item != null);

        return nextValue.length > 0 ? [[key, nextValue]] : [];
      }

      return [[key, value]];
    }),
  );
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
