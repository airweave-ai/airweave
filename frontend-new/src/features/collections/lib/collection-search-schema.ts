import * as z from 'zod';
import {
  collectionSearchFilterOperators,
  collectionSearchFilterableFields,
} from './collection-search-filter';
import {
  collectionSearchInstantRetrievalStrategies,
  collectionSearchTierNames,
} from './collection-search-model';

export const collectionSearchQuerySchema = z
  .string()
  .trim()
  .min(1, 'Ask a question to search this collection.');

export const collectionSearchFilterConditionSchema = z.object({
  field: z.enum(collectionSearchFilterableFields),
  operator: z.enum(collectionSearchFilterOperators),
  value: z.union([
    z.string(),
    z.number(),
    z.boolean(),
    z.array(z.string()),
    z.array(z.number()),
  ]),
});

export const collectionSearchFilterGroupSchema = z.object({
  conditions: z.array(collectionSearchFilterConditionSchema).min(1),
});

export const collectionSearchFiltersSchema = z.array(
  collectionSearchFilterGroupSchema,
);

export const collectionSearchFormSchema = z.object({
  agentic: z.object({
    thinking: z.boolean(),
  }),
  filter: collectionSearchFiltersSchema,
  instant: z.object({
    retrievalStrategy: z.enum(collectionSearchInstantRetrievalStrategies),
  }),
  query: collectionSearchQuerySchema,
  tier: z.enum(collectionSearchTierNames),
});

const collectionSearchSubmitBaseSchema = z.object({
  filter: collectionSearchFiltersSchema,
  query: collectionSearchQuerySchema,
});

const collectionSearchClassicSubmitSchema =
  collectionSearchSubmitBaseSchema.extend({
    tier: z.literal('classic'),
  });

const collectionSearchInstantSubmitSchema =
  collectionSearchSubmitBaseSchema.extend({
    retrievalStrategy: z.enum(collectionSearchInstantRetrievalStrategies),
    tier: z.literal('instant'),
  });

const collectionSearchAgenticSubmitSchema =
  collectionSearchSubmitBaseSchema.extend({
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
