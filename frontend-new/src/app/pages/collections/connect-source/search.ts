import * as z from 'zod';

export const connectSourceAuthSearchSchema = z.object({
  source_connection_id: z.string().optional(),
  status: z.literal('success').optional(),
});

export type ConnectSourceAuthSearch = z.infer<
  typeof connectSourceAuthSearchSchema
>;

export const connectSourceSyncSearchSchema = z.object({
  source_connection_id: z.string(),
});

export type ConnectSourceSyncSearch = z.infer<
  typeof connectSourceSyncSearchSchema
>;
