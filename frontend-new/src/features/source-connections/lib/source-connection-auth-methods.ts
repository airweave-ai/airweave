import type { SourceConnection } from '@/shared/api';

export function isBrowserOAuthMethod(
  method: SourceConnection['auth']['method'],
) {
  return method === 'oauth_browser' || method === 'oauth_byoc';
}
