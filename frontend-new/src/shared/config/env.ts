import * as z from 'zod';

const envSchema = z
  .object({
    VITE_API_URL: z.string().default('http://localhost:8001'),
    VITE_ENABLE_AUTH: z.stringbool().default(false),
    VITE_DEV_IS_ADMIN: z.stringbool().optional(),

    VITE_AUTH0_DOMAIN: z.string().trim().optional(),
    VITE_AUTH0_CLIENT_ID: z.string().trim().optional(),
    VITE_AUTH0_AUDIENCE: z.string().trim().optional(),
  })
  .superRefine((value, ctx) => {
    if (!value.VITE_ENABLE_AUTH) {
      return;
    }

    const requiredFields = [
      'VITE_AUTH0_DOMAIN',
      'VITE_AUTH0_CLIENT_ID',
      'VITE_AUTH0_AUDIENCE',
    ] as const;

    for (const field of requiredFields) {
      if (!value[field]) {
        ctx.addIssue({
          code: 'custom',
          message: `${field} is required when VITE_ENABLE_AUTH=true`,
          path: [field],
        });
      }
    }

    if ('VITE_DEV_IS_ADMIN' in import.meta.env) {
      ctx.addIssue({
        code: 'custom',
        message:
          'VITE_DEV_IS_ADMIN can only be set when VITE_ENABLE_AUTH=false',
        path: ['VITE_DEV_IS_ADMIN'],
      });
    }
  });

export const env = envSchema.parse(import.meta.env);
