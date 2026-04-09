import { getRouteApi } from '@tanstack/react-router';
import type { Source } from '@/shared/api';
import {
  SourcePickerFilters,
  SourcePickerResults,
  useSourcePicker,
} from '@/features/source-connections';
import { DialogDescription, DialogTitle } from '@/shared/ui/dialog';
import {
  FlowDialogAside,
  FlowDialogBody,
  FlowDialogHeader,
  FlowDialogMain,
} from '@/shared/ui/flow-dialog';

const routeApi = getRouteApi(
  '/_authenticated/_app/collections/$collectionId/connect-source/',
);

export function ConnectSourcePickerPage() {
  const navigate = routeApi.useNavigate();
  const { collectionId } = routeApi.useParams();
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
            onSelectSource={(source: Source) =>
              void navigate({
                params: {
                  collectionId,
                  source: source.short_name,
                },
                to: '/collections/$collectionId/connect-source/$source/config',
              })
            }
          />
        </FlowDialogMain>
      </FlowDialogBody>
    </>
  );
}
