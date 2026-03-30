import * as z from 'zod';

export const loginSearchSchema = z.object({
  redirect: z.string().optional(),
  invitation: z.string().optional(),
  organization: z.string().optional(),
  organization_name: z.string().optional(),
});
