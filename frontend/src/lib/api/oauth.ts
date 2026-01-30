/**
 * OAuth API client functions
 */

import { apiClient } from '@/lib/api-client';

export interface OAuthAuthorizationRequest {
  client_id: string;
  redirect_uri: string;
  scope: string;
  state: string;
  code_challenge?: string;
  code_challenge_method?: string;
}

export interface OAuthApprovalRequest {
  approved: boolean;
  collection_id: string;
  client_id: string;
  redirect_uri: string;
  state: string;
  scope: string;
  code_challenge?: string;
  code_challenge_method?: string;
}

/**
 * Approve an OAuth authorization request
 */
export const approveAuthorization = async (request: OAuthApprovalRequest): Promise<void> => {
  const formData = new FormData();
  Object.entries(request).forEach(([key, value]) => {
    if (value !== undefined) {
      formData.append(key, value.toString());
    }
  });

  await apiClient.post('/oauth/authorize', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

/**
 * Deny an OAuth authorization request
 */
export const denyAuthorization = async (
  redirectUri: string,
  state: string
): Promise<string> => {
  return `${redirectUri}?error=access_denied&state=${state}`;
};

/**
 * Revoke an OAuth access token
 */
export const revokeToken = async (token: string): Promise<void> => {
  const formData = new FormData();
  formData.append('token', token);

  await apiClient.post('/oauth/revoke', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};
