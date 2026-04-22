import * as React from 'react';
import { IconCheck, IconCopy, IconPlus, IconX } from '@tabler/icons-react';
import {
  collectionSearchFilterFieldGroups,
  collectionSearchFilterOperatorLabels,
  formatCollectionSearchFilterValue,
  getCollectionSearchFilterFieldType,
  getCollectionSearchFilterOperators,
  parseCollectionSearchFilterValue,
} from '../../lib/collection-search-filter';
import type {
  FilterGroup,
  FilterOperator,
  FilterableField,
} from '@/shared/api';
import { useCopyToClipboard } from '@/shared/hooks/use-copy-to-clipboard';
import { Button } from '@/shared/ui/button';
import { CodeSnippet } from '@/shared/ui/code-snippet';
import { Input } from '@/shared/ui/input';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select';
import { Separator } from '@/shared/ui/separator';

type CollectionSearchFilterDraftCondition = {
  field: FilterableField | '';
  id: string;
  operator: FilterOperator;
  value: string;
};

type CollectionSearchFilterDraftGroup = {
  conditions: Array<CollectionSearchFilterDraftCondition>;
  id: string;
};

const defaultCollectionSearchFilterOperator: FilterOperator = 'equals';

export function CollectionSearchFilters({
  disabled,
  onApply,
  onCancel,
  value,
}: {
  disabled: boolean;
  onApply: (filter: Array<FilterGroup>) => void;
  onCancel: () => void;
  value: Array<FilterGroup>;
}) {
  const { copied, copy } = useCopyToClipboard();
  const [draftGroups, setDraftGroups] = React.useState<
    Array<CollectionSearchFilterDraftGroup>
  >(() => createCollectionSearchFilterDraftGroups(value));
  const serializedFilter = React.useMemo(
    () => serializeCollectionSearchFilterDraftGroups(draftGroups),
    [draftGroups],
  );
  const jsonPreview = React.useMemo(
    () =>
      JSON.stringify(
        serializeCollectionSearchFilterDraftGroupsForPreview(draftGroups),
        null,
        2,
      ),
    [draftGroups],
  );

  const addCondition = React.useCallback((groupId: string) => {
    setDraftGroups((currentGroups) =>
      currentGroups.map((group) =>
        group.id === groupId
          ? {
              ...group,
              conditions: [
                ...group.conditions,
                createCollectionSearchFilterDraftCondition(),
              ],
            }
          : group,
      ),
    );
  }, []);

  const addGroup = React.useCallback(() => {
    setDraftGroups((currentGroups) => [
      ...currentGroups,
      createCollectionSearchFilterDraftGroup(),
    ]);
  }, []);

  const clearDraft = React.useCallback(() => {
    setDraftGroups([createCollectionSearchFilterDraftGroup()]);
  }, []);

  const handleApply = React.useCallback(() => {
    onApply(serializedFilter);
  }, [onApply, serializedFilter]);

  const removeCondition = React.useCallback(
    (groupId: string, conditionId: string) => {
      setDraftGroups((currentGroups) => {
        const group = currentGroups.find(
          (candidate) => candidate.id === groupId,
        );

        if (!group) {
          return currentGroups;
        }

        if (group.conditions.length === 1) {
          return currentGroups.length === 1
            ? [createCollectionSearchFilterDraftGroup()]
            : currentGroups.filter((candidate) => candidate.id !== groupId);
        }

        return currentGroups.map((candidate) =>
          candidate.id === groupId
            ? {
                ...candidate,
                conditions: candidate.conditions.filter(
                  (condition) => condition.id !== conditionId,
                ),
              }
            : candidate,
        );
      });
    },
    [],
  );

  const updateCondition = React.useCallback(
    ({
      conditionId,
      groupId,
      key,
      nextValue,
    }: {
      conditionId: string;
      groupId: string;
      key: 'field' | 'operator' | 'value';
      nextValue: string;
    }) => {
      setDraftGroups((currentGroups) =>
        currentGroups.map((group) => {
          if (group.id !== groupId) {
            return group;
          }

          return {
            ...group,
            conditions: group.conditions.map((condition) => {
              if (condition.id !== conditionId) {
                return condition;
              }

              const nextCondition = {
                ...condition,
                [key]: nextValue,
              } as CollectionSearchFilterDraftCondition;

              if (key === 'field') {
                const allowedOperators = getCollectionSearchFilterOperators(
                  nextValue as FilterableField,
                );

                if (!allowedOperators.includes(nextCondition.operator)) {
                  nextCondition.operator =
                    allowedOperators[0] ??
                    defaultCollectionSearchFilterOperator;
                }
              }

              return nextCondition;
            }),
          };
        }),
      );
    },
    [],
  );

  return (
    <div className="flex w-full flex-col border-t border-border">
      <div className="flex max-h-[min(40vh,26rem)] flex-col overflow-hidden lg:flex-row">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div className="flex flex-wrap items-center gap-3">
              <p className="font-mono text-xs font-medium text-muted-foreground uppercase">
                Filters
              </p>

              <Separator orientation="vertical" className="h-5 bg-border" />

              <p className="font-mono text-xs text-muted-foreground">
                Conditions AND · Groups OR
              </p>
            </div>

            <Button
              className="text-muted-foreground hover:text-secondary-foreground"
              disabled={disabled}
              onClick={clearDraft}
              size="xs"
              type="button"
              variant="secondary"
            >
              Clear
            </Button>
          </div>

          <div className="min-h-0 overflow-y-auto px-4 pb-4">
            <div className="space-y-2">
              {draftGroups.map((group, groupIndex) => (
                <div key={group.id} className="space-y-2">
                  {groupIndex > 0 ? (
                    <div className="mb-4 flex items-center gap-3">
                      <Separator className="flex-1 bg-border" />

                      <span className="font-mono text-xs font-medium text-muted-foreground">
                        OR
                      </span>

                      <Separator className="flex-1 bg-border" />
                    </div>
                  ) : null}

                  <div className="space-y-2">
                    {group.conditions.map((condition, conditionIndex) => (
                      <div
                        key={condition.id}
                        className="flex items-start justify-between gap-3"
                      >
                        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1">
                          {conditionIndex > 0 ? (
                            <span className="px-1 font-mono text-xs font-medium text-muted-foreground">
                              AND
                            </span>
                          ) : null}

                          <Select
                            disabled={disabled}
                            value={condition.field || undefined}
                            onValueChange={(nextValue) =>
                              updateCondition({
                                conditionId: condition.id,
                                groupId: group.id,
                                key: 'field',
                                nextValue,
                              })
                            }
                          >
                            <SelectTrigger
                              size="xs"
                              className="w-32 border-none px-2.5 text-sm"
                            >
                              <SelectValue placeholder="Field" />
                            </SelectTrigger>

                            <SelectContent className="max-h-80">
                              {collectionSearchFilterFieldGroups.map(
                                (fieldGroup, index) => (
                                  <React.Fragment key={fieldGroup.label}>
                                    {index > 0 ? <SelectSeparator /> : null}

                                    <SelectGroup>
                                      <SelectLabel>
                                        {fieldGroup.label}
                                      </SelectLabel>

                                      {fieldGroup.options.map((option) => (
                                        <SelectItem
                                          key={option.value}
                                          value={option.value}
                                        >
                                          {option.label}
                                        </SelectItem>
                                      ))}
                                    </SelectGroup>
                                  </React.Fragment>
                                ),
                              )}
                            </SelectContent>
                          </Select>

                          <Select
                            disabled={disabled}
                            value={condition.operator}
                            onValueChange={(nextValue) =>
                              updateCondition({
                                conditionId: condition.id,
                                groupId: group.id,
                                key: 'operator',
                                nextValue,
                              })
                            }
                          >
                            <SelectTrigger
                              size="xs"
                              className="w-14 rounded-sm border-none px-2.5 text-sm"
                            >
                              <SelectValue />
                            </SelectTrigger>

                            <SelectContent>
                              {getCollectionSearchFilterOperators(
                                condition.field,
                              ).map((operator) => (
                                <SelectItem key={operator} value={operator}>
                                  {
                                    collectionSearchFilterOperatorLabels[
                                      operator
                                    ]
                                  }
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>

                          <Input
                            className="h-6 max-w-44 flex-1 rounded-sm border-none bg-input/30 px-2.5 text-sm"
                            disabled={disabled}
                            placeholder={getCollectionSearchFilterValuePlaceholder(
                              condition,
                            )}
                            value={condition.value}
                            onChange={(event) =>
                              updateCondition({
                                conditionId: condition.id,
                                groupId: group.id,
                                key: 'value',
                                nextValue: event.target.value,
                              })
                            }
                          />
                        </div>

                        <Button
                          aria-label="Remove filter condition"
                          className="size-6 text-muted-foreground hover:text-foreground"
                          disabled={disabled}
                          onClick={() =>
                            removeCondition(group.id, condition.id)
                          }
                          size="icon-xs"
                          type="button"
                          variant="ghost"
                        >
                          <IconX className="size-3" />
                        </Button>
                      </div>
                    ))}

                    <Button
                      className="h-6 px-2 font-mono text-xs font-medium text-muted-foreground hover:text-foreground"
                      disabled={disabled}
                      onClick={() => addCondition(group.id)}
                      size="xs"
                      type="button"
                      variant="ghost"
                    >
                      <IconPlus className="size-3" />
                      AND
                    </Button>
                  </div>
                </div>
              ))}

              <div className="flex justify-center pt-1">
                <Button
                  className="h-6 px-2 font-mono text-xs font-medium text-muted-foreground hover:text-foreground"
                  disabled={disabled}
                  onClick={addGroup}
                  size="xs"
                  type="button"
                  variant="ghost"
                >
                  <IconPlus className="size-3" />
                  OR [Group]
                </Button>
              </div>
            </div>
          </div>
        </div>

        <div className="flex min-h-0 flex-1 flex-col border-t border-border lg:w-72 lg:flex-none lg:shrink-0 lg:border-t-0 lg:border-l">
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            <p className="font-mono text-xs font-medium text-muted-foreground uppercase">
              JSON
            </p>

            <Button
              aria-label="Copy filter JSON"
              className="size-7 shrink-0 text-muted-foreground hover:text-foreground"
              onClick={() => void copy(jsonPreview)}
              size="icon-xs"
              type="button"
              variant="ghost"
            >
              {copied ? (
                <IconCheck className="size-3.5" />
              ) : (
                <IconCopy className="size-3.5" />
              )}
            </Button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
            <div className="min-h-full">
              <CodeSnippet code={jsonPreview} language="json" />
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3">
        <Button
          className="border-secondary"
          disabled={disabled}
          onClick={onCancel}
          size="xs"
          type="button"
          variant="secondary"
        >
          Cancel
        </Button>

        <Button
          disabled={disabled}
          onClick={handleApply}
          size="xs"
          type="button"
          variant="default"
        >
          Apply
        </Button>
      </div>
    </div>
  );
}

function createCollectionSearchFilterDraftCondition(
  value?: FilterGroup['conditions'][number],
): CollectionSearchFilterDraftCondition {
  return {
    field: value?.field ?? '',
    id: crypto.randomUUID(),
    operator: value?.operator ?? defaultCollectionSearchFilterOperator,
    value: value ? formatCollectionSearchFilterValue(value.value) : '',
  };
}

function createCollectionSearchFilterDraftGroup(
  value?: FilterGroup,
): CollectionSearchFilterDraftGroup {
  return {
    conditions:
      value?.conditions.length != null && value.conditions.length > 0
        ? value.conditions.map(createCollectionSearchFilterDraftCondition)
        : [createCollectionSearchFilterDraftCondition()],
    id: crypto.randomUUID(),
  };
}

function createCollectionSearchFilterDraftGroups(value: Array<FilterGroup>) {
  return value.length > 0
    ? value.map(createCollectionSearchFilterDraftGroup)
    : [createCollectionSearchFilterDraftGroup()];
}

function getCollectionSearchFilterValuePlaceholder(
  condition: CollectionSearchFilterDraftCondition,
) {
  if (condition.operator === 'in' || condition.operator === 'not_in') {
    return 'Value-1, Value-2';
  }

  const fieldType = getCollectionSearchFilterFieldType(condition.field);

  if (fieldType === 'date') {
    return '2026-01-01T00:00:00Z';
  }

  if (fieldType === 'numeric') {
    return '0';
  }

  return 'Value...';
}

function isCollectionSearchFilterDraftConditionComplete(
  condition: CollectionSearchFilterDraftCondition,
): condition is CollectionSearchFilterDraftCondition & {
  field: FilterableField;
} {
  return condition.field !== '' && condition.value.trim().length > 0;
}

function serializeCollectionSearchFilterDraftCondition(
  condition: CollectionSearchFilterDraftCondition,
) {
  if (!isCollectionSearchFilterDraftConditionComplete(condition)) {
    return null;
  }

  return {
    field: condition.field,
    operator: condition.operator,
    value: serializeCollectionSearchFilterDraftConditionValue({
      field: condition.field,
      operator: condition.operator,
      value: condition.value,
    }),
  };
}

function serializeCollectionSearchFilterDraftGroups(
  draftGroups: Array<CollectionSearchFilterDraftGroup>,
) {
  return draftGroups
    .map((group) => ({
      conditions: group.conditions.flatMap((condition) => {
        const serializedCondition =
          serializeCollectionSearchFilterDraftCondition(condition);

        return serializedCondition ? [serializedCondition] : [];
      }),
    }))
    .filter((group) => group.conditions.length > 0);
}

function serializeCollectionSearchFilterDraftGroupsForPreview(
  draftGroups: Array<CollectionSearchFilterDraftGroup>,
) {
  return draftGroups.map((group) => ({
    conditions: group.conditions.map((condition) => {
      const serializedCondition =
        serializeCollectionSearchFilterDraftCondition(condition);

      if (serializedCondition) {
        return serializedCondition;
      }

      return {
        field: condition.field || '<field>',
        operator: condition.operator,
        value: getCollectionSearchFilterPreviewValue(condition),
      };
    }),
  }));
}

function serializeCollectionSearchFilterDraftConditionValue({
  field,
  operator,
  value,
}: {
  field: FilterableField;
  operator: FilterOperator;
  value: string;
}) {
  return parseCollectionSearchFilterValue({
    field,
    operator,
    value,
  });
}

function getCollectionSearchFilterPreviewValue(
  condition: CollectionSearchFilterDraftCondition,
) {
  const normalizedValue = condition.value.trim();

  if (normalizedValue.length === 0) {
    return condition.operator === 'in' || condition.operator === 'not_in'
      ? ['<value-1>', '<value-2>']
      : '<value>';
  }

  if (condition.field !== '') {
    return serializeCollectionSearchFilterDraftConditionValue({
      field: condition.field,
      operator: condition.operator,
      value: condition.value,
    });
  }

  if (condition.operator === 'in' || condition.operator === 'not_in') {
    return normalizedValue
      .split(',')
      .map((entry) => entry.trim())
      .filter(Boolean);
  }

  return normalizedValue;
}
