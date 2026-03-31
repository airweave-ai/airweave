import * as z from 'zod';

export const collectionsSearchSchema = z.object({
  search: z
    .string()
    .optional()
    .transform((value) => {
      const normalizedValue = value?.trim();

      return normalizedValue ? normalizedValue : undefined;
    }),
});
