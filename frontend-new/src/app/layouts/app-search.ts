import * as z from 'zod';

const settingsPageSchema = z.enum(['account', 'people', 'usage', 'billing']);

export const appDialogSearchSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('create-collection') }),
  z.object({
    type: z.literal('settings'),
    page: settingsPageSchema,
  }),
]);

export const appSearchSchema = z.object({
  dialog: appDialogSearchSchema.optional(),
});

export type AppSearch = z.infer<typeof appSearchSchema>;
export type SettingsPage = z.infer<typeof settingsPageSchema>;
