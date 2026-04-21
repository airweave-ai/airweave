import * as React from 'react';
import { IconArrowRight, IconPlayerStopFilled } from '@tabler/icons-react';
import { CollectionTooltipContent } from '../collection-tooltip-content';
import {
  collectionSearchTierLabels,
  collectionSearchTierNames,
} from '../../lib/collection-search-model';
import { CollectionSearchState } from './collection-search-state';
import { SearchConfigFields } from './search-config-fields';
import type { CollectionSearchTabValue } from './collection-search-state';
import type { CollectionSearchTiers } from './use-collection-search-tiers';
import type { CollectionSearchWorkspaceForm } from './use-collection-search-workspace';
import type { CollectionSearchTierName } from '../../lib/collection-search-model';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from '@/shared/ui/input-group';
import { Tabs, TabsList, TabsTrigger } from '@/shared/ui/tabs';
import { Tooltip, TooltipTrigger } from '@/shared/ui/tooltip';

const collectionSearchTierTooltipContent: Record<
  CollectionSearchTierName,
  {
    delay: string;
    description: string;
    title: string;
  }
> = {
  agentic: {
    delay: '<2 min',
    description:
      'Agent that navigates through your collection to find the best results',
    title: 'Agentic',
  },
  classic: {
    delay: '~2s',
    description: 'AI-optimized search strategy',
    title: 'Classic',
  },
  instant: {
    delay: '~0.5s',
    description: 'Direct vector search',
    title: 'Instant',
  },
};

export function CollectionSearch({
  disabled = false,
  form,
  tiers,
}: {
  disabled?: boolean;
  form: CollectionSearchWorkspaceForm;
  tiers: CollectionSearchTiers;
}) {
  const [selectedTabsByTier, setSelectedTabsByTier] = React.useState<
    Partial<Record<CollectionSearchTierName, CollectionSearchTabValue>>
  >({});

  const handleSelectedTabChange = React.useCallback(
    (tier: CollectionSearchTierName, tab: CollectionSearchTabValue) => {
      setSelectedTabsByTier((currentTabs) => {
        if (currentTabs[tier] === tab) {
          return currentTabs;
        }

        return {
          ...currentTabs,
          [tier]: tab,
        };
      });
    },
    [],
  );

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        return form.handleSubmit();
      }}
    >
      <form.Subscribe
        selector={(state) => ({
          tier: state.values.tier,
        })}
      >
        {({ tier }) => {
          const activeTier = tiers[tier];
          const isLoading = activeTier.state.status === 'loading';
          const activeSelectedTab = selectedTabsByTier[tier];

          return (
            <React.Fragment>
              <div className="space-y-2">
                <InputGroup className="rounded-sm border-none">
                  <form.Field name="query">
                    {(field) => {
                      const query = field.state.value;

                      return (
                        <InputGroupTextarea
                          disabled={disabled}
                          placeholder="Ask your agent a question..."
                          value={query}
                          className="min-h-21 px-4 pt-4 pb-2 text-sm leading-5 placeholder:text-muted-foreground"
                          onBlur={field.handleBlur}
                          onChange={(event) => {
                            field.handleChange(event.target.value);
                          }}
                          onKeyDown={(event) => {
                            if (
                              event.key !== 'Enter' ||
                              event.shiftKey ||
                              event.nativeEvent.isComposing
                            ) {
                              return;
                            }

                            event.preventDefault();

                            if (
                              !disabled &&
                              !isLoading &&
                              form.state.canSubmit
                            ) {
                              return form.handleSubmit();
                            }
                          }}
                        />
                      );
                    }}
                  </form.Field>

                  <InputGroupAddon
                    align="block-end"
                    className="w-full flex-wrap items-center justify-between gap-3 px-4 pb-4"
                  >
                    <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1">
                      <form.Field name="tier">
                        {(field) => (
                          <Tabs
                            className="shrink-0"
                            value={field.state.value}
                            onValueChange={(value) => {
                              const nextTier =
                                value as CollectionSearchTierName;

                              if (nextTier === tier) {
                                return;
                              }

                              if (activeTier.state.status === 'loading') {
                                activeTier.cancel();
                              }

                              field.handleChange(nextTier);
                            }}
                          >
                            <TabsList
                              aria-label="Search tier"
                              className="!h-9 w-64"
                            >
                              {collectionSearchTierNames.map((tierName) => {
                                const tooltip =
                                  collectionSearchTierTooltipContent[tierName];

                                return (
                                  <Tooltip key={tierName}>
                                    <TooltipTrigger asChild>
                                      <div className="flex flex-1">
                                        <TabsTrigger
                                          className="w-full"
                                          disabled={disabled}
                                          value={tierName}
                                        >
                                          {collectionSearchTierLabels[tierName]}
                                        </TabsTrigger>
                                      </div>
                                    </TooltipTrigger>

                                    <CollectionTooltipContent
                                      sideOffset={8}
                                      description={tooltip.description}
                                      footer={tooltip.delay}
                                      title={tooltip.title}
                                    />
                                  </Tooltip>
                                );
                              })}
                            </TabsList>
                          </Tabs>
                        )}
                      </form.Field>

                      <SearchConfigFields
                        disabled={disabled}
                        form={form}
                        tier={tier}
                      />
                    </div>

                    <form.Subscribe selector={(state) => state.canSubmit}>
                      {(canSubmit) => {
                        const buttonClassName = 'size-9 rounded-xs';

                        if (isLoading) {
                          return (
                            <InputGroupButton
                              aria-label="Cancel search"
                              disabled={disabled}
                              size="icon-sm"
                              type="button"
                              variant="destructive"
                              className={buttonClassName}
                              onClick={() => {
                                activeTier.cancel();
                              }}
                            >
                              <IconPlayerStopFilled className="size-4" />
                            </InputGroupButton>
                          );
                        }

                        return (
                          <InputGroupButton
                            aria-label="Search collection"
                            disabled={disabled || !canSubmit}
                            size="icon-sm"
                            type="submit"
                            variant="default"
                            className={buttonClassName}
                          >
                            <IconArrowRight className="size-4" />
                          </InputGroupButton>
                        );
                      }}
                    </form.Subscribe>
                  </InputGroupAddon>
                </InputGroup>
              </div>

              <CollectionSearchState
                onSelectedTabChange={(tab) =>
                  handleSelectedTabChange(tier, tab)
                }
                selectedTab={activeSelectedTab}
                state={activeTier.state}
                tierName={tier}
              />
            </React.Fragment>
          );
        }}
      </form.Subscribe>
    </form>
  );
}
