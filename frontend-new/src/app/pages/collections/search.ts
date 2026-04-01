import * as z from 'zod';
import { connectSourceStepSchema } from '../components/connect-source-state';

export const collectionsSearchSchema = z.object({
  connectSource: connectSourceStepSchema.optional(),
  search: z.string().default(''),
});

export type CollectionsSearch = z.infer<typeof collectionsSearchSchema>;
