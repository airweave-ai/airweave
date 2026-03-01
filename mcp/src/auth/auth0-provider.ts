import type { Response } from 'express';
import { createRemoteJWKSet, jwtVerify } from 'jose';
import type { OAuthServerProvider, AuthorizationParams } from '@modelcontextprotocol/sdk/server/auth/provider.js';
import type {
    OAuthClientInformationFull,
    OAuthTokenRevocationRequest,
    OAuthTokens
} from '@modelcontextprotocol/sdk/shared/auth.js';
import type { AuthInfo } from '@modelcontextprotocol/sdk/server/auth/types.js';
import { RedisRegisteredClientsStore } from './registered-clients-store.js';
import { OAuthTransactionStore } from './oauth-transaction-store.js';

type Auth0TokenResponse = OAuthTokens & {
    id_token?: string;
};

function requiredEnv(name: string): string {
    const value = process.env[name];
    if (!value) {
        throw new Error(`Missing required env var: ${name}`);
    }
    return value;
}

function toUrl(base: string, path: string): URL {
    return new URL(path, base.endsWith('/') ? base : `${base}/`);
}

export class Auth0OAuthProvider implements OAuthServerProvider {
    public readonly skipLocalPkceValidation = true;
    public readonly clientsStore = new RedisRegisteredClientsStore();
    private readonly txStore = new OAuthTransactionStore();

    private readonly auth0Domain = requiredEnv('AUTH0_DOMAIN');
    private readonly auth0ClientId = requiredEnv('AUTH0_CLIENT_ID');
    private readonly auth0ClientSecret = requiredEnv('AUTH0_CLIENT_SECRET');
    private readonly auth0Audience = requiredEnv('AUTH0_AUDIENCE');
    private readonly mcpBaseUrl = requiredEnv('MCP_BASE_URL');

    private readonly jwks = createRemoteJWKSet(
        new URL(`https://${this.auth0Domain}/.well-known/jwks.json`)
    );

    async authorize(
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
        res: Response
    ): Promise<void> {
        const pending = await this.txStore.createPendingAuthorization({
            clientId: client.client_id,
            redirectUri: params.redirectUri,
            codeChallenge: params.codeChallenge,
            state: params.state,
            scopes: params.scopes || [],
        });

        const callbackUrl = toUrl(this.mcpBaseUrl, '/oauth/callback');
        const authorizeUrl = new URL(`https://${this.auth0Domain}/authorize`);
        authorizeUrl.searchParams.set('response_type', 'code');
        authorizeUrl.searchParams.set('client_id', this.auth0ClientId);
        authorizeUrl.searchParams.set('redirect_uri', callbackUrl.toString());
        authorizeUrl.searchParams.set('audience', this.auth0Audience);
        authorizeUrl.searchParams.set('state', pending.id);
        authorizeUrl.searchParams.set(
            'scope',
            params.scopes?.length ? params.scopes.join(' ') : 'openid profile email offline_access'
        );

        res.redirect(302, authorizeUrl.toString());
    }

    async challengeForAuthorizationCode(
        client: OAuthClientInformationFull,
        authorizationCode: string
    ): Promise<string> {
        const codeRecord = await this.txStore.getAuthorizationCode(authorizationCode);
        if (!codeRecord || codeRecord.clientId !== client.client_id) {
            throw new Error('Invalid authorization code');
        }
        return codeRecord.codeChallenge;
    }

    async exchangeAuthorizationCode(
        client: OAuthClientInformationFull,
        authorizationCode: string,
        _codeVerifier?: string,
        redirectUri?: string
    ): Promise<OAuthTokens> {
        const codeRecord = await this.txStore.consumeAuthorizationCode(authorizationCode);
        if (!codeRecord) {
            throw new Error('Invalid or expired authorization code');
        }
        if (codeRecord.clientId !== client.client_id) {
            throw new Error('Authorization code was not issued to this client');
        }
        if (redirectUri && redirectUri !== codeRecord.redirectUri) {
            throw new Error('Redirect URI mismatch');
        }
        return {
            ...codeRecord.tokens,
            token_type: codeRecord.tokens.token_type || 'Bearer',
        };
    }

    async exchangeRefreshToken(
        _client: OAuthClientInformationFull,
        refreshToken: string,
        scopes?: string[]
    ): Promise<OAuthTokens> {
        const tokenUrl = new URL(`https://${this.auth0Domain}/oauth/token`);
        const body = {
            grant_type: 'refresh_token',
            refresh_token: refreshToken,
            client_id: this.auth0ClientId,
            client_secret: this.auth0ClientSecret,
            ...(scopes?.length ? { scope: scopes.join(' ') } : {}),
        };

        const response = await fetch(tokenUrl, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!response.ok) {
            throw new Error(`Auth0 refresh failed with status ${response.status}`);
        }
        const tokens = await response.json() as OAuthTokens;
        return {
            ...tokens,
            token_type: tokens.token_type || 'Bearer',
        };
    }

    async verifyAccessToken(token: string): Promise<AuthInfo> {
        const { payload } = await jwtVerify(token, this.jwks, {
            issuer: `https://${this.auth0Domain}/`,
            audience: this.auth0Audience,
        });

        const scopeStr = typeof payload.scope === 'string' ? payload.scope : '';
        const scopes = scopeStr.length > 0 ? scopeStr.split(' ') : [];
        const expiresAt = typeof payload.exp === 'number' ? payload.exp : undefined;
        const clientId = (
            typeof payload.azp === 'string'
                ? payload.azp
                : typeof payload.client_id === 'string'
                    ? payload.client_id
                    : 'auth0'
        );

        return {
            token,
            clientId,
            scopes,
            expiresAt,
            extra: {
                sub: payload.sub,
                email: payload.email,
                org_id: payload.org_id,
            },
        };
    }

    async revokeToken(
        _client: OAuthClientInformationFull,
        request: OAuthTokenRevocationRequest
    ): Promise<void> {
        const revokeUrl = new URL(`https://${this.auth0Domain}/oauth/revoke`);
        await fetch(revokeUrl, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({
                client_id: this.auth0ClientId,
                client_secret: this.auth0ClientSecret,
                token: request.token,
            }),
        });
    }

    async exchangeAuth0CodeForLocalCode(
        pendingStateId: string,
        auth0Code: string
    ): Promise<{ code: string; redirectUri: string; state?: string; tokens: Auth0TokenResponse }> {
        const pending = await this.txStore.getPendingAuthorization(pendingStateId);
        if (!pending) {
            throw new Error('Invalid or expired OAuth state');
        }

        const tokenUrl = new URL(`https://${this.auth0Domain}/oauth/token`);
        const callbackUrl = toUrl(this.mcpBaseUrl, '/oauth/callback');
        const tokenResponse = await fetch(tokenUrl, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({
                grant_type: 'authorization_code',
                code: auth0Code,
                client_id: this.auth0ClientId,
                client_secret: this.auth0ClientSecret,
                redirect_uri: callbackUrl.toString(),
            }),
        });

        if (!tokenResponse.ok) {
            const errorBody = await tokenResponse.text();
            console.error(`[${new Date().toISOString()}] Auth0 token exchange error:`, {
                status: tokenResponse.status,
                body: errorBody,
                redirect_uri: callbackUrl.toString(),
            });
            throw new Error(`Auth0 code exchange failed with status ${tokenResponse.status}: ${errorBody}`);
        }

        const tokens = await tokenResponse.json() as Auth0TokenResponse;
        const codeRecord = await this.txStore.issueAuthorizationCode({
            clientId: pending.clientId,
            redirectUri: pending.redirectUri,
            codeChallenge: pending.codeChallenge,
            scopes: pending.scopes,
            tokens: {
                access_token: tokens.access_token,
                refresh_token: tokens.refresh_token,
                token_type: tokens.token_type || 'Bearer',
                expires_in: tokens.expires_in,
                scope: tokens.scope,
            },
        });

        await this.txStore.deletePendingAuthorization(pending.id);
        return {
            code: codeRecord.id,
            redirectUri: pending.redirectUri,
            state: pending.state,
            tokens,
        };
    }
}
