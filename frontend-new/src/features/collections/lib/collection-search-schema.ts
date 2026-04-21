import * as z from 'zod';
import {
  collectionSearchInstantRetrievalStrategies,
  collectionSearchTierNames,
} from './collection-search-model';

export const collectionSearchQuerySchema = z
  .string()
  .trim()
  .min(1, 'Ask a question to search this collection.');

export const collectionSearchFormSchema = z.object({
  agentic: z.object({
    thinking: z.boolean(),
  }),
  instant: z.object({
    retrievalStrategy: z.enum(collectionSearchInstantRetrievalStrategies),
  }),
  query: collectionSearchQuerySchema,
  tier: z.enum(collectionSearchTierNames),
});

const collectionSearchClassicSubmitSchema = z.object({
  query: collectionSearchQuerySchema,
  tier: z.literal('classic'),
});

const collectionSearchInstantSubmitSchema = z.object({
  query: collectionSearchQuerySchema,
  retrievalStrategy: z.enum(collectionSearchInstantRetrievalStrategies),
  tier: z.literal('instant'),
});

const collectionSearchAgenticSubmitSchema = z.object({
  query: collectionSearchQuerySchema,
  thinking: z.boolean(),
  tier: z.literal('agentic'),
});

export const collectionSearchSubmitSchema = z.discriminatedUnion('tier', [
  collectionSearchClassicSubmitSchema,
  collectionSearchInstantSubmitSchema,
  collectionSearchAgenticSubmitSchema,
]);

export type CollectionSearchSubmitValues = z.output<
  typeof collectionSearchSubmitSchema
>;
