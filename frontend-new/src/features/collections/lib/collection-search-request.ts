import {
  isCollectionSearchFilterEqual,
  normalizeCollectionSearchFilter,
} from './collection-search-filter';
import { defaultCollectionSearchConfig } from './collection-search-model';
import { collectionSearchSubmitSchema } from './collection-search-schema';
import type {
  CollectionSearchConfig,
  CollectionSearchFormValues,
  CollectionSearchTierName,
} from './collection-search-model';
import type { CollectionSearchSubmitValues } from './collection-search-schema';

export type ClassicCollectionSearchRequest = {
  collectionId: string;
  filter?: CollectionSearchConfig['filter'];
  query: string;
  tier: 'classic';
};

export type InstantCollectionSearchRequest = {
  collectionId: string;
  filter?: CollectionSearchConfig['filter'];
  query: string;
  retrievalStrategy: CollectionSearchConfig['instant']['retrievalStrategy'];
  tier: 'instant';
};

export type AgenticCollectionSearchRequest = {
  collectionId: string;
  filter?: CollectionSearchConfig['filter'];
  query: string;
  thinking: boolean;
  tier: 'agentic';
};

export type CollectionSearchRequest =
  | AgenticCollectionSearchRequest
  | ClassicCollectionSearchRequest
  | InstantCollectionSearchRequest;

export function getCollectionSearchConfig(
  values: Pick<
    CollectionSearchFormValues,
    'agentic' | 'filter' | 'instant' | 'tier'
  >,
): CollectionSearchConfig {
  return {
    agentic: {
      thinking: values.agentic.thinking,
    },
    filter: values.filter,
    instant: {
      retrievalStrategy: values.instant.retrievalStrategy,
    },
    tier: values.tier,
  };
}

export function getCollectionSearchSubmitValues(
  values: CollectionSearchFormValues,
): CollectionSearchSubmitValues {
  switch (values.tier) {
    case 'classic':
      return collectionSearchSubmitSchema.parse({
        filter: values.filter,
        query: values.query,
        tier: values.tier,
      });
    case 'instant':
      return collectionSearchSubmitSchema.parse({
        filter: values.filter,
        query: values.query,
        retrievalStrategy: values.instant.retrievalStrategy,
        tier: values.tier,
      });
    case 'agentic':
      return collectionSearchSubmitSchema.parse({
        filter: values.filter,
        query: values.query,
        thinking: values.agentic.thinking,
        tier: values.tier,
      });
  }
}

export function createCollectionSearchRequest({
  collectionId,
  values,
}: {
  collectionId: string;
  values: CollectionSearchFormValues;
}): CollectionSearchRequest {
  const submitValues = getCollectionSearchSubmitValues(values);
  const filter = normalizeCollectionSearchFilter(submitValues.filter);
  const filterField = filter ? { filter } : {};

  switch (submitValues.tier) {
    case 'classic':
      return {
        collectionId,
        ...filterField,
        query: submitValues.query,
        tier: submitValues.tier,
      };
    case 'instant':
      return {
        collectionId,
        ...filterField,
        query: submitValues.query,
        retrievalStrategy: submitValues.retrievalStrategy,
        tier: submitValues.tier,
      };
    case 'agentic':
      return {
        collectionId,
        ...filterField,
        query: submitValues.query,
        thinking: submitValues.thinking,
        tier: submitValues.tier,
      };
  }
}

export function getDefaultCollectionSearchRequest(
  collectionId: string,
  tier: CollectionSearchTierName,
): CollectionSearchRequest {
  switch (tier) {
    case 'classic':
      return {
        collectionId,
        query: '',
        tier,
      };
    case 'instant':
      return {
        collectionId,
        query: '',
        retrievalStrategy:
          defaultCollectionSearchConfig.instant.retrievalStrategy,
        tier,
      };
    case 'agentic':
      return {
        collectionId,
        query: '',
        thinking: defaultCollectionSearchConfig.agentic.thinking,
        tier,
      };
  }
}

export function isCollectionSearchRequestEqual(
  left: CollectionSearchRequest | null,
  right: CollectionSearchRequest,
): boolean {
  if (
    left === null ||
    left.collectionId !== right.collectionId ||
    !isCollectionSearchFilterEqual(left.filter, right.filter) ||
    left.query !== right.query ||
    left.tier !== right.tier
  ) {
    return false;
  }

  switch (left.tier) {
    case 'classic':
      return true;
    case 'instant':
      return (
        right.tier === 'instant' &&
        left.retrievalStrategy === right.retrievalStrategy
      );
    case 'agentic':
      return right.tier === 'agentic' && left.thinking === right.thinking;
  }
}
