import type { AirweaveDomainsSearchTypesPlanRetrievalStrategy } from '@/shared/api';

export const collectionSearchTierNames = [
  'instant',
  'classic',
  'agentic',
] as const;

export type CollectionSearchTierName =
  (typeof collectionSearchTierNames)[number];

export const collectionSearchTierLabels: Record<
  CollectionSearchTierName,
  string
> = {
  instant: 'Instant',
  classic: 'Classic',
  agentic: 'Agentic',
};

export const collectionSearchInstantRetrievalStrategies = [
  'semantic',
  'keyword',
  'hybrid',
] as const satisfies ReadonlyArray<AirweaveDomainsSearchTypesPlanRetrievalStrategy>;

export type CollectionSearchInstantRetrievalStrategy =
  (typeof collectionSearchInstantRetrievalStrategies)[number];

export const collectionSearchInstantRetrievalStrategyLabels: Record<
  CollectionSearchInstantRetrievalStrategy,
  string
> = {
  semantic: 'Semantic',
  keyword: 'Keyword',
  hybrid: 'Hybrid',
};

export type CollectionSearchConfig = {
  agentic: {
    thinking: boolean;
  };
  instant: {
    retrievalStrategy: CollectionSearchInstantRetrievalStrategy;
  };
  tier: CollectionSearchTierName;
};

export type CollectionSearchFormValues = CollectionSearchConfig & {
  query: string;
};

export const defaultCollectionSearchConfig: CollectionSearchConfig = {
  agentic: {
    thinking: false,
  },
  instant: {
    retrievalStrategy: 'hybrid',
  },
  tier: 'classic',
};

export const defaultCollectionSearchFormValues: CollectionSearchFormValues = {
  query: '',
  ...defaultCollectionSearchConfig,
};
