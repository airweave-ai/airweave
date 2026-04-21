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
  query: string;
  tier: 'classic';
};

export type InstantCollectionSearchRequest = {
  collectionId: string;
  query: string;
  retrievalStrategy: CollectionSearchConfig['instant']['retrievalStrategy'];
  tier: 'instant';
};

export type AgenticCollectionSearchRequest = {
  collectionId: string;
  query: string;
  thinking: boolean;
  tier: 'agentic';
};

export type CollectionSearchRequest =
  | AgenticCollectionSearchRequest
  | ClassicCollectionSearchRequest
  | InstantCollectionSearchRequest;

export function getCollectionSearchConfig(
  values: Pick<CollectionSearchFormValues, 'agentic' | 'instant' | 'tier'>,
): CollectionSearchConfig {
  return {
    agentic: {
      thinking: values.agentic.thinking,
    },
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
        query: values.query,
        tier: values.tier,
      });
    case 'instant':
      return collectionSearchSubmitSchema.parse({
        query: values.query,
        retrievalStrategy: values.instant.retrievalStrategy,
        tier: values.tier,
      });
    case 'agentic':
      return collectionSearchSubmitSchema.parse({
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

  switch (submitValues.tier) {
    case 'classic':
      return {
        collectionId,
        ...submitValues,
      };
    case 'instant':
      return {
        collectionId,
        ...submitValues,
      };
    case 'agentic':
      return {
        collectionId,
        ...submitValues,
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
