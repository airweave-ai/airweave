import type { SourceConnection } from '@/shared/api';

type ConnectSourceAuthAsyncStatus = 'idle' | 'pending' | 'success' | 'error';

export type ConnectSourceAuthState =
  | { kind: 'loading-connection' }
  | { kind: 'callback-invalid' }
  | { kind: 'connection-error'; message: string }
  | {
      kind: 'authorize-ready';
      authUrl: string;
      authUrlExpiresAt: string | null;
    }
  | { kind: 'verifying-return' }
  | { kind: 'reauthorize-required' }
  | { kind: 'reauthorizing' }
  | { kind: 'reauthorize-failed'; message: string }
  | { kind: 'blocking-missing-claim-token' }
  | { kind: 'verify-failed'; message: string }
  | { kind: 'unknown-authenticated' };

interface DeriveConnectSourceAuthStateInput {
  callbackStatus?: string;
  claimToken: string | null;
  expectedCollectionId: string;
  expectedSource: string;
  sourceConnection: SourceConnection | null;
  sourceConnectionErrorMessage?: string;
  sourceConnectionId?: string;
  isConnectionLoading: boolean;
  reauthorizeErrorMessage?: string;
  reauthorizeStatus: ConnectSourceAuthAsyncStatus;
  verifyErrorMessage?: string;
  verifyStatus: ConnectSourceAuthAsyncStatus;
}

export function deriveConnectSourceAuthState({
  callbackStatus,
  claimToken,
  expectedCollectionId,
  expectedSource,
  isConnectionLoading,
  reauthorizeErrorMessage,
  reauthorizeStatus,
  sourceConnection,
  sourceConnectionErrorMessage,
  sourceConnectionId,
  verifyErrorMessage,
  verifyStatus,
}: DeriveConnectSourceAuthStateInput): ConnectSourceAuthState {
  if (callbackStatus && callbackStatus !== 'success') {
    return { kind: 'callback-invalid' };
  }

  if (callbackStatus === 'success' && !sourceConnectionId) {
    return { kind: 'callback-invalid' };
  }

  if (!sourceConnectionId) {
    return {
      kind: 'connection-error',
      message: 'Missing source connection id in auth route.',
    };
  }

  if (isConnectionLoading) {
    return { kind: 'loading-connection' };
  }

  if (sourceConnectionErrorMessage || !sourceConnection) {
    return {
      kind: 'connection-error',
      message:
        sourceConnectionErrorMessage ??
        'Could not load the source connection details.',
    };
  }

  if (!isBrowserOAuthMethod(sourceConnection.auth.method)) {
    return {
      kind: 'connection-error',
      message: 'This source connection does not use browser OAuth.',
    };
  }

  if (sourceConnection.readable_collection_id !== expectedCollectionId) {
    return {
      kind: 'connection-error',
      message: 'This source connection does not belong to this collection.',
    };
  }

  if (sourceConnection.short_name !== expectedSource) {
    return {
      kind: 'connection-error',
      message: 'This source connection does not match the current source route.',
    };
  }

  if (verifyStatus === 'pending') {
    return { kind: 'verifying-return' };
  }

  if (verifyStatus === 'error') {
    return {
      kind: 'verify-failed',
      message: verifyErrorMessage ?? 'Could not verify the OAuth callback.',
    };
  }

  if (reauthorizeStatus === 'pending') {
    return { kind: 'reauthorizing' };
  }

  if (reauthorizeStatus === 'error') {
    return {
      kind: 'reauthorize-failed',
      message:
        reauthorizeErrorMessage ??
        'Could not create a fresh authorization link.',
    };
  }

  if (callbackStatus === 'success') {
    if (!sourceConnection.auth.authenticated) {
      return { kind: 'callback-invalid' };
    }

    if (!claimToken) {
      return { kind: 'blocking-missing-claim-token' };
    }

    return { kind: 'verifying-return' };
  }

  if (sourceConnection.auth.authenticated) {
    return { kind: 'unknown-authenticated' };
  }

  if (sourceConnection.auth.auth_url) {
    return {
      kind: 'authorize-ready',
      authUrl: sourceConnection.auth.auth_url,
      authUrlExpiresAt: sourceConnection.auth.auth_url_expires ?? null,
    };
  }

  return { kind: 'reauthorize-required' };
}

export function shouldAutoVerifyConnectSourceAuthReturn({
  callbackStatus,
  claimToken,
  sourceConnection,
  sourceConnectionId,
  verifyStatus,
}: {
  callbackStatus?: string;
  claimToken: string | null;
  sourceConnection: SourceConnection | null;
  sourceConnectionId?: string;
  verifyStatus: ConnectSourceAuthAsyncStatus;
}) {
  if (
    callbackStatus !== 'success' ||
    !claimToken ||
    !sourceConnection ||
    !sourceConnectionId ||
    verifyStatus !== 'idle'
  ) {
    return false;
  }

  return (
    sourceConnection.auth.authenticated &&
    isBrowserOAuthMethod(sourceConnection.auth.method)
  );
}

function isBrowserOAuthMethod(method: SourceConnection['auth']['method']) {
  return method === 'oauth_browser' || method === 'oauth_byoc';
}
