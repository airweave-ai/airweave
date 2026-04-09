const CONNECT_SOURCE_AUTH_CLAIM_TOKEN_PREFIX = 'oauth_claim_token:';

function getConnectSourceAuthClaimTokenKey(sourceConnectionId: string) {
  return `${CONNECT_SOURCE_AUTH_CLAIM_TOKEN_PREFIX}${sourceConnectionId}`;
}

export function getConnectSourceAuthClaimToken(sourceConnectionId: string) {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.sessionStorage.getItem(
    getConnectSourceAuthClaimTokenKey(sourceConnectionId),
  );
}

export function setConnectSourceAuthClaimToken(
  sourceConnectionId: string,
  claimToken: string,
) {
  if (typeof window === 'undefined') {
    return;
  }

  window.sessionStorage.setItem(
    getConnectSourceAuthClaimTokenKey(sourceConnectionId),
    claimToken,
  );
}

export function clearConnectSourceAuthClaimToken(sourceConnectionId: string) {
  if (typeof window === 'undefined') {
    return;
  }

  window.sessionStorage.removeItem(
    getConnectSourceAuthClaimTokenKey(sourceConnectionId),
  );
}
