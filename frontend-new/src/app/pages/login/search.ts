import * as z from 'zod';

export const loginSearchSchema = z.object({
  redirect: z.string().optional(),
});

export type LoginSearch = z.infer<typeof loginSearchSchema>;
