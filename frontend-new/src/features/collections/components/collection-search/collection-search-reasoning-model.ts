import type {
  FilterOperator,
  FilterableField,
  SearchAgenticDoneEvent,
  SearchAgenticStreamEvent,
} from '@/shared/api';
import { formatNumber } from '@/shared/format/format-number';
import { pluralize } from '@/shared/format/pluralize';

const FIELD_SHORT_NAMES = {
  'airweave_system_metadata.chunk_index': 'chunk',
  'airweave_system_metadata.entity_type': 'type',
  'airweave_system_metadata.original_entity_id': 'original_id',
  'airweave_system_metadata.source_name': 'source',
  'breadcrumbs.entity_id': 'breadcrumb_id',
  'breadcrumbs.entity_type': 'breadcrumb_type',
  'breadcrumbs.name': 'breadcrumb',
} as const satisfies Partial<Record<FilterableField, string>>;

const OP_SYMBOLS = {
  contains: '~',
  equals: '=',
  greater_than: '>',
  greater_than_or_equal: '>=',
  in: 'in',
  less_than: '<',
  less_than_or_equal: '<=',
  not_equals: '!=',
  not_in: 'not in',
} as const satisfies Record<FilterOperator, string>;

type CollectionSearchReasoningToolLabelKey =
  | Exclude<
      Extract<CollectionSearchReasoningEvent, { type: 'tool_call' }>['tool_kind'],
      'unknown'
    >
  | 'reranking';

const TOOL_LABELS = {
  add_to_results: 'Collect',
  count: 'Count',
  get_children: 'GetChildren',
  get_parent: 'GetParent',
  get_siblings: 'GetSiblings',
  hybrid_search: 'HybridSearch',
  keyword_search: 'KeywordSearch',
  read: 'Read',
  remove_from_results: 'Remove',
  reranking: 'Rerank',
  return_results_to_user: 'Return',
  review_results: 'Review',
  semantic_search: 'SemanticSearch',
} as const satisfies Record<CollectionSearchReasoningToolLabelKey, string>;

type CollectionSearchReasoningEvent = Extract<
  SearchAgenticStreamEvent,
  { type: 'thinking' | 'tool_call' | 'reranking' }
>;

type CollectionSearchReasoningEntity = {
  entity_id?: string;
  entity_type?: string;
  name?: string;
  relevance_score?: number | null;
  source_name?: string;
};

type CollectionSearchReasoningFilterCondition = {
  field?: string;
  operator?: string;
  value?: unknown;
};

type CollectionSearchReasoningFilterGroup = {
  conditions: Array<CollectionSearchReasoningFilterCondition>;
};

export type CollectionSearchReasoningSection = {
  collapsed: string;
  expandedLines: Array<CollectionSearchReasoningExpandedLine>;
  label: 'input' | 'output';
};

export type CollectionSearchReasoningExpandedLine =
  | {
      content: string;
      type: 'text';
    }
  | {
      label: string;
      metadata: string;
      type: 'entity';
    };

export type CollectionSearchReasoningRow = {
  detailLines?: Array<string>;
  isInvalid?: boolean;
  label: string;
  labelSuffix?: string;
  metaLabel?: string;
  sections?: Array<CollectionSearchReasoningSection>;
};

export function formatCollectionSearchReasoningEvent(
  event: CollectionSearchReasoningEvent,
): CollectionSearchReasoningRow | null {
  switch (event.type) {
    case 'thinking':
      return {
        detailLines: [
          event.text ??
            event.thinking ??
            'Working through the query and planning the next step.',
        ],
        label: formatThoughtTitle(event.duration_ms),
        metaLabel: formatThinkingTokenSummary(event.diagnostics),
      };

    case 'tool_call':
      return formatToolCallReasoningEvent(event);

    case 'reranking':
      return {
        label: TOOL_LABELS.reranking,
        labelSuffix: `${formatOptionalNumber(event.diagnostics.input_count)} results`,
        metaLabel: formatElapsedDuration(event.duration_ms),
        sections: event.diagnostics.first_results.length
          ? [
              {
                collapsed: formatRerankResultList(event.diagnostics.first_results),
                expandedLines: formatEntityExpandedLines(
                  event.diagnostics.first_results,
                  undefined,
                  true,
                ),
                label: 'output',
              },
            ]
          : undefined,
      };
  }
}

export function getCollectionSearchReasoningSummarySections(
  finalEvent?: SearchAgenticDoneEvent,
) {
  if (!finalEvent) {
    return [];
  }

  const foundCount = finalEvent.diagnostics?.all_seen_entity_ids.length ?? finalEvent.results.length;
  const readCount = finalEvent.diagnostics?.all_read_entity_ids.length ?? 0;
  const collectedCount = finalEvent.diagnostics?.all_collected_entity_ids.length ?? 0;
  const promptTokens = finalEvent.diagnostics?.prompt_tokens ?? 0;
  const completionTokens = finalEvent.diagnostics?.completion_tokens ?? 0;
  const cachedTokens =
    (finalEvent.diagnostics?.cache_creation_input_tokens ?? 0) +
    (finalEvent.diagnostics?.cache_read_input_tokens ?? 0);

  const sections = [
    `${formatNumber(foundCount)} found · ${formatNumber(readCount)} read · ${formatNumber(collectedCount)} collected`,
  ];

  if (promptTokens > 0 || completionTokens > 0 || cachedTokens > 0) {
    const tokenSummaryParts = [
      `${formatNumber(promptTokens)} input`,
      `${formatNumber(completionTokens)} output tokens`,
    ];

    if (cachedTokens > 0) {
      tokenSummaryParts.push(`${formatNumber(cachedTokens)} cached`);
    }

    sections.push(tokenSummaryParts.join(' · '));
  }

  sections.push(`${formatElapsedDuration(finalEvent.duration_ms)} total`);

  return sections;
}

function formatToolCallReasoningEvent(
  event: Extract<CollectionSearchReasoningEvent, { type: 'tool_call' }>,
): CollectionSearchReasoningRow | null {
  if (event.tool_kind === 'return_results_to_user') {
    return null;
  }

  if ('error' in event.diagnostics.stats && typeof event.diagnostics.stats.error === 'string') {
    return {
      isInvalid: true,
      label: getToolLabel(event),
      labelSuffix: 'invalid input',
      metaLabel: formatElapsedDuration(event.duration_ms),
    };
  }

  const sections: Array<CollectionSearchReasoningSection> = [];
  let labelSuffix: string | undefined;

  switch (event.tool_kind) {
    case 'semantic_search':
    case 'keyword_search':
    case 'hybrid_search': {
      const primaryQuery = event.diagnostics.arguments.query?.primary ?? '';
      const variations = event.diagnostics.arguments.query?.variations ?? [];
      const filterGroups = event.diagnostics.arguments.filter_groups;
      const resultCount = event.diagnostics.stats.result_count;
      const newResults = event.diagnostics.stats.new_results ?? 0;

      labelSuffix =
        resultCount !== undefined
          ? newResults > 0 && newResults < resultCount
            ? `${formatNumber(resultCount)} results (${formatNumber(newResults)} new)`
            : `${formatNumber(resultCount)} results`
          : '? results';

      const inputParts = [primaryQuery ? `"${primaryQuery}"` : ''].filter(Boolean);
      if (variations.length > 0) {
        inputParts.push(
          `${formatNumber(variations.length)} ${pluralize(variations.length, 'variation')}`,
        );
      }

      const totalConditions = getTotalFilterConditions(filterGroups);
      if (totalConditions === 1 && filterGroups.length === 1) {
        const firstCondition = filterGroups[0]?.conditions[0];
        if (firstCondition) {
          inputParts.push(formatCondition(firstCondition));
        }
      } else if (totalConditions > 0) {
        inputParts.push(`${formatNumber(totalConditions)} filters`);
      }

      pushReasoningSection(
        sections,
        'input',
        inputParts.join('  '),
        [
          primaryQuery ? `query: "${primaryQuery}"` : undefined,
          ...formatVariationLines(variations),
          ...formatFilterGroupLines(filterGroups),
          formatLimitOffsetLine(
            event.diagnostics.arguments.limit,
            event.diagnostics.arguments.offset,
          ),
        ].filter((line): line is string => Boolean(line)),
      );

      pushReasoningSection(
        sections,
        'output',
        formatEntityList(
          event.diagnostics.stats.first_results,
          event.diagnostics.stats.result_count,
        ),
        formatEntityExpandedLines(
          event.diagnostics.stats.first_results,
          event.diagnostics.stats.result_count,
        ),
      );
      break;
    }

    case 'read': {
      labelSuffix = `${formatOptionalNumber(event.diagnostics.stats.found)} entities`;

      if (event.diagnostics.stats.entities.length > 0) {
        const expandedLines = formatEntityExpandedLines(
          event.diagnostics.stats.entities,
          event.diagnostics.stats.found,
        );
        if ((event.diagnostics.stats.not_found ?? 0) > 0) {
          expandedLines.push({
            content: `${formatNumber(event.diagnostics.stats.not_found ?? 0)} not found`,
            type: 'text',
          });
        }

        pushReasoningSection(
          sections,
          'output',
          formatEntityList(
            event.diagnostics.stats.entities,
            event.diagnostics.stats.found,
          ),
          expandedLines,
        );
      } else if (event.diagnostics.arguments.entity_ids.length > 0) {
        pushReasoningSection(sections, 'input', 'entity IDs', [
          event.diagnostics.arguments.entity_ids.join(', '),
        ]);
      }
      break;
    }

    case 'add_to_results': {
      const added =
        event.diagnostics.stats.added ?? event.diagnostics.stats.entities.length;

      labelSuffix = `${formatOptionalNumber(added)} added (${formatOptionalNumber(event.diagnostics.stats.total_collected)} total)`;

      if (event.diagnostics.stats.entities.length > 0) {
        const expandedLines = formatEntityExpandedLines(
          event.diagnostics.stats.entities,
          added,
        );
        if ((event.diagnostics.stats.not_found ?? 0) > 0) {
          expandedLines.push({
            content: `${formatNumber(event.diagnostics.stats.not_found ?? 0)} not found`,
            type: 'text',
          });
        }

        pushReasoningSection(
          sections,
          'output',
          formatEntityList(event.diagnostics.stats.entities, added),
          expandedLines,
        );
      } else if (event.diagnostics.arguments.entity_ids.length > 0) {
        const expandedLines = [event.diagnostics.arguments.entity_ids.join(', ')];
        if ((event.diagnostics.stats.not_found ?? 0) > 0) {
          expandedLines.push(
            `${formatNumber(event.diagnostics.stats.not_found ?? 0)} not found`,
          );
        }

        pushReasoningSection(sections, 'input', 'entity IDs', expandedLines);
      }
      break;
    }

    case 'remove_from_results': {
      const removedCount = event.diagnostics.arguments.entity_ids.length > 0
        ? formatNumber(event.diagnostics.arguments.entity_ids.length)
        : '?';

      labelSuffix = `${removedCount} removed (${formatOptionalNumber(event.diagnostics.stats.total_collected)} total)`;

      if (event.diagnostics.stats.entities.length > 0) {
        pushReasoningSection(
          sections,
          'input',
          formatEntityList(
            event.diagnostics.stats.entities,
            event.diagnostics.arguments.entity_ids.length || undefined,
          ),
          formatEntityExpandedLines(event.diagnostics.stats.entities),
        );
      } else if (event.diagnostics.arguments.entity_ids.length > 0) {
        pushReasoningSection(sections, 'input', 'entity IDs', [
          event.diagnostics.arguments.entity_ids.join(', '),
        ]);
      }
      break;
    }

    case 'count': {
      const totalConditions = getTotalFilterConditions(
        event.diagnostics.arguments.filter_groups,
      );

      labelSuffix = `${formatOptionalNumber(event.diagnostics.stats.count)} matches`;

      if (totalConditions > 0) {
        pushReasoningSection(
          sections,
          'input',
          `${formatNumber(totalConditions)} filter${totalConditions > 1 ? 's' : ''}`,
          formatFilterGroupLines(event.diagnostics.arguments.filter_groups),
        );
      }
      break;
    }

    case 'get_children':
    case 'get_siblings': {
      labelSuffix = `${formatOptionalNumber(event.diagnostics.stats.result_count)} results`;

      pushReasoningSection(
        sections,
        'input',
        event.diagnostics.stats.context_label ?? `"${event.diagnostics.arguments.entity_id ?? '?'}"`,
        [],
      );
      pushReasoningSection(
        sections,
        'output',
        formatEntityList(
          event.diagnostics.stats.first_results,
          event.diagnostics.stats.result_count,
        ),
        formatEntityExpandedLines(
          event.diagnostics.stats.first_results,
          event.diagnostics.stats.result_count,
        ),
      );
      break;
    }

    case 'get_parent': {
      const found = event.diagnostics.stats.found;

      labelSuffix = `${formatOptionalNumber(found)} found`;

      pushReasoningSection(
        sections,
        'input',
        event.diagnostics.stats.context_label ?? `"${event.diagnostics.arguments.entity_id ?? '?'}"`,
        [],
      );
      pushReasoningSection(
        sections,
        'output',
        formatEntityList(event.diagnostics.stats.entities, found),
        formatEntityExpandedLines(event.diagnostics.stats.entities, found),
      );
      break;
    }

    case 'review_results': {
      labelSuffix = `${formatOptionalNumber(event.diagnostics.stats.total_collected)} collected`;

      pushReasoningSection(
        sections,
        'input',
        formatEntityList(
          event.diagnostics.stats.first_results,
          event.diagnostics.stats.total_collected,
        ),
        formatEntityExpandedLines(
          event.diagnostics.stats.first_results,
          event.diagnostics.stats.total_collected,
        ),
      );
      break;
    }

    case 'unknown':
      break;

    default:
      return null;
  }

  return {
    label: getToolLabel(event),
    labelSuffix,
    metaLabel: formatElapsedDuration(event.duration_ms),
    sections,
  };
}

function pushReasoningSection(
  sections: Array<CollectionSearchReasoningSection>,
  label: CollectionSearchReasoningSection['label'],
  collapsed: string,
  expandedLines: Array<
    string | CollectionSearchReasoningExpandedLine
  >,
) {
  if (!collapsed) {
    return;
  }

  sections.push({
    collapsed,
    expandedLines: expandedLines.map(normalizeCollectionSearchReasoningExpandedLine),
    label,
  });
}

function getToolLabel(
  event: Extract<CollectionSearchReasoningEvent, { type: 'tool_call' }>,
) {
  return event.tool_kind === 'unknown' ? event.tool_name : TOOL_LABELS[event.tool_kind];
}

function shortenField(field: string) {
  return isCollectionSearchReasoningShortField(field)
    ? FIELD_SHORT_NAMES[field]
    : field;
}

function formatCondition(condition: CollectionSearchReasoningFilterCondition) {
  const field = shortenField(condition.field ?? '');
  const operator =
    condition.operator && isCollectionSearchReasoningFilterOperator(condition.operator)
      ? OP_SYMBOLS[condition.operator]
      : condition.operator ?? '?';
  const rawValue = condition.value;

  if (typeof rawValue === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(rawValue)) {
    return `${field} ${operator} ${rawValue.split('T')[0]}`;
  }

  if (Array.isArray(rawValue)) {
    return `${field} ${operator} [${rawValue.join(', ')}]`;
  }

  return `${field} ${operator} ${String(rawValue)}`;
}

function formatFilterGroupLines(
  filterGroups: Array<CollectionSearchReasoningFilterGroup>,
) {
  return filterGroups.flatMap((group, groupIndex) => {
    const conditions = group.conditions.map(formatCondition);
    if (conditions.length === 0) {
      return [];
    }

    return [`${groupIndex > 0 ? 'OR ' : ''}${conditions.join(' AND ')}`];
  });
}

function getTotalFilterConditions(
  filterGroups: Array<CollectionSearchReasoningFilterGroup>,
) {
  return filterGroups.reduce(
    (sum, group) => sum + group.conditions.length,
    0,
  );
}

function formatVariationLines(variations: Array<string>) {
  if (variations.length === 0) {
    return [];
  }

  return ['variations:', ...variations.map((variation) => `"${variation}"`)];
}

function formatLimitOffsetLine(limit?: number, offset?: number) {
  const parts = [
    limit ? `limit: ${formatNumber(limit)}` : undefined,
    offset ? `offset: ${formatNumber(offset)}` : undefined,
  ].filter((part): part is string => Boolean(part));

  return parts.length > 0 ? parts.join('  ') : undefined;
}

function formatEntityList(
  entities: Array<CollectionSearchReasoningEntity>,
  totalCount?: number,
) {
  if (entities.length === 0) {
    return '';
  }

  const parts = entities.slice(0, 2).map((entity) => {
    const name = entity.name ?? '';
    const sourceName = entity.source_name ?? '?';
    const truncatedName = name.length > 30 ? `${name.slice(0, 27)}...` : name;

    return `${truncatedName || 'Unknown entity'} (${sourceName})`;
  });

  const total = totalCount ?? entities.length;
  const remaining = total - parts.length;
  if (remaining > 0) {
    parts.push(`+${formatNumber(remaining)} more`);
  }

  return parts.join(', ');
}

function formatRerankResultList(
  results: Array<CollectionSearchReasoningEntity>,
  maxChars = 100,
) {
  if (results.length === 0) {
    return '';
  }

  const parts: Array<string> = [];
  let totalLength = 0;

  for (const result of results) {
    const name = result.name ?? 'Unknown entity';
    const truncatedName = name.length > 20 ? `${name.slice(0, 17)}...` : name;
    const part = `${truncatedName} (${result.relevance_score?.toFixed(2) ?? '?'})`;

    if (parts.length > 0 && totalLength + part.length + 2 > maxChars) {
      break;
    }

    parts.push(part);
    totalLength += part.length + 2;
  }

  return parts.join(', ');
}

function formatEntityExpandedLines(
  entities: Array<CollectionSearchReasoningEntity>,
  totalCount?: number,
  includeScore = false,
) {
  const lines: Array<CollectionSearchReasoningExpandedLine> = entities.map(
    (entity) => {
    const name = entity.name ?? 'Unknown entity';
    const sourceName = entity.source_name ?? '?';
    const entityType = entity.entity_type ?? '?';
    const entityId = entity.entity_id ?? '?';

    if (includeScore) {
      return {
        label: name,
        metadata: ` (${sourceName} · ${entityType} · ${entityId} · score: ${entity.relevance_score?.toFixed(3) ?? '?'})`,
        type: 'entity' as const,
      };
    }

    return {
      label: name,
      metadata: ` (${sourceName} · ${entityType} · ${entityId})`,
      type: 'entity' as const,
    };
    },
  );

  if (totalCount !== undefined && totalCount > entities.length) {
    lines.push({
      content: `+${formatNumber(totalCount - entities.length)} more`,
      type: 'text',
    });
  }

  return lines;
}

function formatThinkingTokenSummary(
  diagnostics: Extract<CollectionSearchReasoningEvent, { type: 'thinking' }>['diagnostics'],
) {
  if (
    diagnostics.prompt_tokens === undefined &&
    diagnostics.completion_tokens === undefined
  ) {
    return undefined;
  }

  if (
    diagnostics.prompt_tokens !== undefined &&
    diagnostics.completion_tokens !== undefined
  ) {
    return `${formatNumber(diagnostics.prompt_tokens)}-${formatNumber(diagnostics.completion_tokens)} tokens`;
  }

  return `${formatNumber(diagnostics.prompt_tokens ?? diagnostics.completion_tokens ?? 0)} tokens`;
}

function formatElapsedDuration(durationMs: number) {
  if (durationMs < 1000) {
    return `${formatNumber(durationMs)}ms`;
  }

  return `${formatNumber(durationMs / 1000, {
    maximumFractionDigits: 1,
  })}s`;
}

function formatThoughtTitle(durationMs: number) {
  if (durationMs <= 0) {
    return 'Thought';
  }

  return `Thought for ${formatNumber(durationMs / 1000, {
    maximumFractionDigits: 1,
  })}s`;
}

function formatOptionalNumber(value?: number) {
  return value === undefined ? '?' : formatNumber(value);
}

function normalizeCollectionSearchReasoningExpandedLine(
  expandedLine: string | CollectionSearchReasoningExpandedLine,
): CollectionSearchReasoningExpandedLine {
  return typeof expandedLine === 'string'
    ? { content: expandedLine, type: 'text' }
    : expandedLine;
}

function isCollectionSearchReasoningShortField(
  field: string,
): field is keyof typeof FIELD_SHORT_NAMES {
  return field in FIELD_SHORT_NAMES;
}

function isCollectionSearchReasoningFilterOperator(
  operator: string,
): operator is keyof typeof OP_SYMBOLS {
  return operator in OP_SYMBOLS;
}
