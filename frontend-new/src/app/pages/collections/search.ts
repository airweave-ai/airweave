import * as z from 'zod';

export const collectionsSearchSchema = z.object({
  search: z.string().default(''),
});

export type CollectionsSearch = z.infer<typeof collectionsSearchSchema>;
