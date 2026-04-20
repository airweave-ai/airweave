import type { ApiKey } from '@/shared/api';
import { normalizeSearchQuery } from '@/shared/search/normalize-search-query';

export function filterApiKeys(apiKeys: Array<ApiKey>, search?: string) {
  const normalizedSearch = normalizeSearchQuery(search)?.toLowerCase();

  if (!normalizedSearch) {
    return apiKeys;
  }

  return apiKeys.filter((apiKey) => {
    const searchableText = [
      apiKey.id,
      apiKey.decrypted_key,
      apiKey.created_by_email,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();

    return searchableText.includes(normalizedSearch);
  });
}
