import * as z from 'zod';

export const trimmedStringSchema = z.string().trim();

export const optionalTrimmedStringSchema = z
  .string()
  .optional()
  .transform((value) => {
    const trimmedValue = value?.trim();

    return trimmedValue === '' ? undefined : trimmedValue;
  });
