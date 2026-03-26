export type Result<TData, TError = unknown> =
  | { data: TData; error: null }
  | { data: null; error: TError };
