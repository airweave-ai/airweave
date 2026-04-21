import {
  collectionSearchInstantRetrievalStrategies,
  collectionSearchInstantRetrievalStrategyLabels,
} from '../../lib/collection-search-model';
import { CollectionTooltipContent } from '../collection-tooltip-content';
import type {
  CollectionSearchInstantRetrievalStrategy,
  CollectionSearchTierName,
} from '../../lib/collection-search-model';
import type { CollectionSearchWorkspaceForm } from './use-collection-search-workspace';
import { cn } from '@/shared/tailwind/cn';
import { Field, FieldLabel } from '@/shared/ui/field';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select';
import { Switch } from '@/shared/ui/switch';
import { Tooltip, TooltipTrigger } from '@/shared/ui/tooltip';

export function SearchConfigFields({
  disabled,
  form,
  tier,
}: {
  disabled: boolean;
  form: CollectionSearchWorkspaceForm;
  tier: CollectionSearchTierName;
}) {
  if (tier === 'classic') {
    return null;
  }

  if (tier === 'instant') {
    return (
      <form.Field name="instant.retrievalStrategy">
        {(field) => (
          <Select
            disabled={disabled}
            value={field.state.value}
            onValueChange={(value) =>
              field.handleChange(
                value as CollectionSearchInstantRetrievalStrategy,
              )
            }
          >
            <SelectTrigger
              aria-label="Retrieval strategy"
              id="search-instant-retrieval-strategy"
              className="!h-9 w-32 rounded-sm border-none"
            >
              <SelectValue
                aria-label={
                  collectionSearchInstantRetrievalStrategyLabels[
                    field.state
                      .value as CollectionSearchInstantRetrievalStrategy
                  ]
                }
              />
            </SelectTrigger>

            <SelectContent position="popper">
              {collectionSearchInstantRetrievalStrategies.map((strategy) => (
                <SelectItem key={strategy} value={strategy}>
                  {collectionSearchInstantRetrievalStrategyLabels[strategy]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </form.Field>
    );
  }

  return (
    <form.Field name="agentic.thinking">
      {(field) => (
        <Tooltip>
          <TooltipTrigger asChild>
            <Field
              data-disabled={disabled || undefined}
              orientation="horizontal"
              className="h-9 w-auto items-center gap-2 px-2"
              onClick={(e) => e.stopPropagation()}
            >
              <Switch
                checked={field.state.value}
                disabled={disabled}
                id="search-agentic-thinking"
                onCheckedChange={field.handleChange}
              />

              <FieldLabel
                htmlFor="search-agentic-thinking"
                className={cn(
                  'flex-none font-normal',
                  field.state.value
                    ? 'text-foreground'
                    : 'text-muted-foreground',
                )}
              >
                Thinking
              </FieldLabel>
            </Field>
          </TooltipTrigger>

          <CollectionTooltipContent
            sideOffset={8}
            description="Extended reasoning, the agent thinks more carefully"
            footer="<5 min"
            title="Thinking"
          />
        </Tooltip>
      )}
    </form.Field>
  );
}
