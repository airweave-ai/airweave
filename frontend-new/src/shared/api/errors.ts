import * as z from 'zod';

// TODO: in the future, consider updating backend OpenAPI error responses to expose
// typed schemas with stable machine-readable error codes, not only free-form
// `detail` strings. That would let frontend code narrow errors from generated
// types directly and avoid local parsing helpers like this one.
const apiErrorWithDetailSchema = z.object({
  detail: z.string(),
});

const apiValidationErrorSchema = z.object({
  detail: z.array(
    z.object({
      msg: z.string(),
    }),
  ),
});

export type ApiErrorWithDetail = z.infer<typeof apiErrorWithDetailSchema>;

export function parseApiErrorWithDetail(error: unknown) {
  const result = apiErrorWithDetailSchema.safeParse(error);

  if (!result.success) {
    return null;
  }

  return result.data;
}

export function hasApiErrorDetail(error: unknown, detail: string) {
  const parsedError = parseApiErrorWithDetail(error);

  return parsedError?.detail === detail;
}

export function getApiErrorMessage(error: unknown, fallbackMessage: string) {
  if (!error) {
    return undefined;
  }

  const parsedError = parseApiErrorWithDetail(error);

  if (typeof parsedError?.detail === 'string' && parsedError.detail) {
    return parsedError.detail;
  }

  const parsedValidationError = apiValidationErrorSchema.safeParse(error);

  if (
    parsedValidationError.success &&
    parsedValidationError.data.detail.length > 0
  ) {
    return parsedValidationError.data.detail
      .map((detail) => detail.msg)
      .join(', ');
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallbackMessage;
}
