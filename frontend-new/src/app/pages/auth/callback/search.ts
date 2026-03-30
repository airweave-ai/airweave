import * as z from 'zod';

export const callbackSearchSchema = z.object({
  redirect: z.string().optional(),
  organization_name: z.string().optional(),
});
