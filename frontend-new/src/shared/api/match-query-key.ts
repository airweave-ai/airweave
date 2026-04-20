import * as z from 'zod';
import type { Query } from '@tanstack/react-query';

type QueryKeyFilters = {
  tags: ReadonlyArray<string>;
};

const queryKeyWithTagsSchema = z.object({
  tags: z.array(z.string()),
});

export function matchQueryKey(filters: QueryKeyFilters) {
  return (query: Query) => {
    const [queryKey] = query.queryKey;
    const parseResult = queryKeyWithTagsSchema.safeParse(queryKey);

    if (!parseResult.success) {
      return false;
    }

    for (const tag of parseResult.data.tags) {
      if (filters.tags.includes(tag)) {
        return true;
      }
    }
    return false;
  };
}
