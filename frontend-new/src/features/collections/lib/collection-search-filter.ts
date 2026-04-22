import type {
  FilterCondition,
  FilterGroup,
  FilterOperator,
  FilterableField,
} from '@/shared/api';

type CollectionSearchFilterFieldType = 'date' | 'numeric' | 'text';

export type CollectionSearchFilterFieldOption = {
  category: 'Base' | 'Breadcrumbs' | 'Metadata';
  label: string;
  value: FilterableField;
};

export const collectionSearchFilterableFields = [
  'entity_id',
  'name',
  'created_at',
  'updated_at',
  'breadcrumbs.entity_id',
  'breadcrumbs.name',
  'breadcrumbs.entity_type',
  'airweave_system_metadata.entity_type',
  'airweave_system_metadata.source_name',
  'airweave_system_metadata.original_entity_id',
  'airweave_system_metadata.chunk_index',
  'airweave_system_metadata.sync_id',
  'airweave_system_metadata.sync_job_id',
] as const satisfies ReadonlyArray<FilterableField>;

export const collectionSearchFilterOperators = [
  'equals',
  'not_equals',
  'contains',
  'greater_than',
  'less_than',
  'greater_than_or_equal',
  'less_than_or_equal',
  'in',
  'not_in',
] as const satisfies ReadonlyArray<FilterOperator>;

export const collectionSearchFilterFieldOptions: Array<
  CollectionSearchFilterFieldOption
> = [
  { category: 'Base', label: 'Name', value: 'name' },
  { category: 'Base', label: 'Entity ID', value: 'entity_id' },
  { category: 'Base', label: 'Created at', value: 'created_at' },
  { category: 'Base', label: 'Updated at', value: 'updated_at' },
  {
    category: 'Breadcrumbs',
    label: 'Breadcrumb name',
    value: 'breadcrumbs.name',
  },
  {
    category: 'Breadcrumbs',
    label: 'Breadcrumb ID',
    value: 'breadcrumbs.entity_id',
  },
  {
    category: 'Breadcrumbs',
    label: 'Breadcrumb type',
    value: 'breadcrumbs.entity_type',
  },
  {
    category: 'Metadata',
    label: 'Source',
    value: 'airweave_system_metadata.source_name',
  },
  {
    category: 'Metadata',
    label: 'Entity type',
    value: 'airweave_system_metadata.entity_type',
  },
  {
    category: 'Metadata',
    label: 'Original ID',
    value: 'airweave_system_metadata.original_entity_id',
  },
  {
    category: 'Metadata',
    label: 'Chunk index',
    value: 'airweave_system_metadata.chunk_index',
  },
  {
    category: 'Metadata',
    label: 'Sync ID',
    value: 'airweave_system_metadata.sync_id',
  },
  {
    category: 'Metadata',
    label: 'Sync job ID',
    value: 'airweave_system_metadata.sync_job_id',
  },
];

export const collectionSearchFilterFieldGroups = [
  {
    label: 'Base',
    options: collectionSearchFilterFieldOptions.filter(
      (option) => option.category === 'Base',
    ),
  },
  {
    label: 'Breadcrumbs',
    options: collectionSearchFilterFieldOptions.filter(
      (option) => option.category === 'Breadcrumbs',
    ),
  },
  {
    label: 'Metadata',
    options: collectionSearchFilterFieldOptions.filter(
      (option) => option.category === 'Metadata',
    ),
  },
] as const;

export const collectionSearchFilterOperatorLabels: Record<
  FilterOperator,
  string
> = {
  contains: '∋',
  equals: '=',
  greater_than: '>',
  greater_than_or_equal: '≥',
  in: 'in',
  less_than: '<',
  less_than_or_equal: '≤',
  not_equals: '≠',
  not_in: '∉',
};

const collectionSearchFilterFieldTypes: Record<
  FilterableField,
  CollectionSearchFilterFieldType
> = {
  'airweave_system_metadata.chunk_index': 'numeric',
  'airweave_system_metadata.entity_type': 'text',
  'airweave_system_metadata.original_entity_id': 'text',
  'airweave_system_metadata.source_name': 'text',
  'airweave_system_metadata.sync_id': 'text',
  'airweave_system_metadata.sync_job_id': 'text',
  'breadcrumbs.entity_id': 'text',
  'breadcrumbs.entity_type': 'text',
  'breadcrumbs.name': 'text',
  created_at: 'date',
  entity_id: 'text',
  name: 'text',
  updated_at: 'date',
};

const collectionSearchFilterOperatorsByFieldType: Record<
  CollectionSearchFilterFieldType,
  Array<FilterOperator>
> = {
  date: [
    'equals',
    'not_equals',
    'greater_than',
    'less_than',
    'greater_than_or_equal',
    'less_than_or_equal',
  ],
  numeric: [
    'equals',
    'not_equals',
    'greater_than',
    'less_than',
    'greater_than_or_equal',
    'less_than_or_equal',
    'in',
    'not_in',
  ],
  text: ['equals', 'not_equals', 'contains', 'in', 'not_in'],
};

export function normalizeCollectionSearchFilter(filter: Array<FilterGroup>) {
  return filter.length > 0 ? filter : undefined;
}

export function getCollectionSearchFilterFieldType(
  field: FilterableField | '',
) {
  return field ? collectionSearchFilterFieldTypes[field] : undefined;
}

export function getCollectionSearchFilterOperators(
  field: FilterableField | '',
) {
  const fieldType = getCollectionSearchFilterFieldType(field);

  return fieldType
    ? collectionSearchFilterOperatorsByFieldType[fieldType]
    : [...collectionSearchFilterOperators];
}

export function formatCollectionSearchFilterValue(
  value: FilterCondition['value'],
) {
  return Array.isArray(value) ? value.join(', ') : String(value);
}

export function parseCollectionSearchFilterValue({
  field,
  operator,
  value,
}: {
  field: FilterableField;
  operator: FilterOperator;
  value: string;
}): FilterCondition['value'] {
  const normalizedValue = value.trim();

  if (operator === 'in' || operator === 'not_in') {
    const values = normalizedValue
      .split(',')
      .map((entry) => entry.trim())
      .filter(Boolean);

    return getCollectionSearchFilterFieldType(field) === 'numeric' &&
      values.every(isNumericValue)
      ? values.map(Number)
      : values;
  }

  if (
    getCollectionSearchFilterFieldType(field) === 'numeric' &&
    isNumericValue(normalizedValue)
  ) {
    return Number(normalizedValue);
  }

  if (normalizedValue === 'true') {
    return true;
  }

  if (normalizedValue === 'false') {
    return false;
  }

  return normalizedValue;
}

export function isCollectionSearchFilterEqual(
  left: Array<FilterGroup> | undefined,
  right: Array<FilterGroup> | undefined,
): boolean {
  return serializeCollectionSearchFilter(left) === serializeCollectionSearchFilter(right);
}

function serializeCollectionSearchFilter(filter: Array<FilterGroup> | undefined) {
  return filter && filter.length > 0 ? JSON.stringify(filter) : '';
}

function isNumericValue(value: string) {
  return value.length > 0 && Number.isFinite(Number(value));
}
