import * as z from 'zod';

export const appDialogSearchSchema = z.object({
  type: z.literal('create-collection'),
});

export const appSearchSchema = z.object({
  dialog: appDialogSearchSchema.optional(),
});

export type AppSearch = z.infer<typeof appSearchSchema>;
