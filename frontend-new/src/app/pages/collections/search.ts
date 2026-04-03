import * as z from 'zod';
import { connectSourceStepSchema } from '@/features/source-connections';

export const collectionsSearchSchema = z.object({
  connectSource: connectSourceStepSchema.optional(),
  search: z.string().default(''),
});

export type CollectionsSearch = z.infer<typeof collectionsSearchSchema>;
