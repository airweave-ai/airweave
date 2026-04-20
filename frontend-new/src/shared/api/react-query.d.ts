import '@tanstack/react-query';

interface AppMutationMeta extends Record<string, unknown> {
  errorToast?: string | false;
  invalidateTags?: ReadonlyArray<string>;
}

declare module '@tanstack/react-query' {
  interface Register {
    mutationMeta: AppMutationMeta;
  }
}
