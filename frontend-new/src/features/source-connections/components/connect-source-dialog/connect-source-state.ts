import * as z from 'zod';

export const connectSourceStepSchema = z.discriminatedUnion('step', [
  z.object({
    collectionId: z.string().optional(),
    step: z.literal('source'),
  }),
  z.object({
    collectionId: z.string().optional(),
    source: z.string(),
    step: z.literal('config'),
  }),
  z.object({
    collectionId: z.string(),
    source: z.string(),
    sourceConnectionId: z.string(),
    step: z.literal('auth'),
  }),
  z.object({
    collectionId: z.string(),
    source: z.string(),
    sourceConnectionId: z.string(),
    step: z.literal('sync'),
  }),
]);

export type ConnectSourceStep = z.infer<typeof connectSourceStepSchema>;
