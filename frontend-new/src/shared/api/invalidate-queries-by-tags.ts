import { matchQueryKey } from './match-query-key';
import type { QueryClient } from '@tanstack/react-query';

export async function invalidateQueriesByTags(
  queryClient: QueryClient,
  tags: ReadonlyArray<string>,
) {
  if (tags.length === 0) {
    return;
  }

  await queryClient.invalidateQueries({
    predicate: matchQueryKey({ tags }),
  });
}
