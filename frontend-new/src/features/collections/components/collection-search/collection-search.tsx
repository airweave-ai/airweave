import * as React from 'react';
import { useForm } from '@tanstack/react-form';
import { IconArrowRight, IconPlayerStopFilled } from '@tabler/icons-react';
import * as z from 'zod';
import { CollectionSearchState } from './collection-search-state';
import {
  collectionSearchTierLabels,
  collectionSearchTierNames,
  useCollectionSearchTiers,
} from './use-collection-search-tiers';
import type { CollectionSearchTabValue } from './collection-search-state';
import type { CollectionSearchTierName } from './use-collection-search-tiers';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from '@/shared/ui/input-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select';

const collectionSearchQuerySchema = z
  .string()
  .trim()
  .min(1, 'Ask a question to search this collection.');

const collectionSearchFormSchema = z.object({
  query: collectionSearchQuerySchema,
});

const defaultFormValues = {
  query: '',
};

export function CollectionSearch({
  collectionId,
  disabled = false,
  onTierChange,
  tier,
}: {
  collectionId: string;
  disabled?: boolean;
  onTierChange: (tier: CollectionSearchTierName) => void;
  tier: CollectionSearchTierName;
}) {
  const [selectedTabsByTier, setSelectedTabsByTier] = React.useState<
    Partial<Record<CollectionSearchTierName, CollectionSearchTabValue>>
  >({});
  const tiers = useCollectionSearchTiers({ collectionId });
  const activeTier = tiers[tier];
  const isLoading = activeTier.state.status === 'loading';
  const activeSelectedTab = selectedTabsByTier[tier];

  const form = useForm({
    defaultValues: defaultFormValues,
    validators: {
      onChange: collectionSearchFormSchema,
      onMount: collectionSearchFormSchema,
      onSubmit: collectionSearchFormSchema,
    },
    onSubmit: ({ value }) => {
      const { query } = collectionSearchFormSchema.parse(value);

      activeTier.submit(query);
    },
  });

  const handleSubmit = React.useCallback(() => {
    void form.handleSubmit();
  }, [form]);

  const handleCancel = React.useCallback(() => {
    activeTier.cancel();
  }, [activeTier]);

  const handleTierChange = React.useCallback(
    (nextTierName: CollectionSearchTierName) => {
      if (nextTierName === tier) {
        return;
      }

      if (activeTier.state.status === 'loading') {
        activeTier.cancel();
      }

      onTierChange(nextTierName);
    },
    [activeTier, onTierChange],
  );

  const handleSelectedTabChange = React.useCallback(
    (tab: CollectionSearchTabValue) => {
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
    [tier],
  );

  return (
    <div className="space-y-4">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          handleSubmit();
        }}
      >
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

                      if (!disabled && !isLoading && form.state.canSubmit) {
                        handleSubmit();
                      }
                    }}
                  />
                );
              }}
            </form.Field>

            <InputGroupAddon
              align="block-end"
              className="w-full items-center justify-between gap-3 px-4 pb-4"
            >
              <Select
                disabled={disabled}
                value={tier}
                onValueChange={(value: CollectionSearchTierName) =>
                  handleTierChange(value)
                }
              >
                <SelectTrigger
                  size="sm"
                  className="min-w-23 shrink-0 border-none dark:bg-transparent"
                >
                  <SelectValue aria-label={collectionSearchTierLabels[tier]} />
                </SelectTrigger>

                <SelectContent position="popper">
                  {collectionSearchTierNames.map((tierName) => (
                    <SelectItem key={tierName} value={tierName}>
                      {collectionSearchTierLabels[tierName]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

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
                        onClick={handleCancel}
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
      </form>

      <CollectionSearchState
        onSelectedTabChange={handleSelectedTabChange}
        selectedTab={activeSelectedTab}
        state={activeTier.state}
        tierName={tier}
      />
    </div>
  );
}
