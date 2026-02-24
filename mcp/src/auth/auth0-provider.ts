import { randomUUID } from 'node:crypto';
import { Response } from 'express';
import {
    OAuthClientInformationFull,
    OAuthTokens,
    OAuthTokensSchema
} from '@modelcontextprotocol/sdk/shared/auth.js';
import { OAuthServerProvider, AuthorizationParams } from '@modelcontextprotocol/sdk/server/auth/provider.js';
import { InvalidGrantError, InvalidTokenError, ServerError } from '@modelcontextprotocol/sdk/server/auth/errors.js';
import { AuthInfo } from '@modelcontextprotocol/sdk/server/auth/types.js';
import { createRemoteJWKSet, jwtVerify } from 'jose';
import { InMemoryClientsStore } from './clients-store.js';

export type Auth0ProviderConfig = {
    domain: string;
    clientId: string;
    clientSecret: string;
    audience: string;
    mcpBaseUrl: string;
    defaultScopes?: string[];
};

type PendingAuthorization = {
    clientId: string;
    codeChallenge: string;
    redirectUri: string;
    state?: string;
    scopes: string[];
};

type StoredGrant = {
    clientId: string;
    codeChallenge: string;
    redirectUri: string;
    tokens: OAuthTokens;
};

const DEFAULT_SCOPES = ['openid', 'profile', 'email'];

export class Auth0OAuthServerProvider implements OAuthServerProvider {
    private readonly _clientsStore = new InMemoryClientsStore();
    private readonly pendingAuthorizations = new Map<string, PendingAuthorization>();
    private readonly authorizationCodeGrants = new Map<string, StoredGrant>();
    private readonly defaultScopes: string[];
    private readonly callbackUrl: string;
    private readonly tokenUrl: string;
    private readonly issuer: string;
    private readonly jwks;

    constructor(private readonly config: Auth0ProviderConfig) {
        this.defaultScopes = config.defaultScopes?.length ? config.defaultScopes : DEFAULT_SCOPES;
        this.callbackUrl = `${config.mcpBaseUrl.replace(/\/$/, '')}/auth0/callback`;
        this.tokenUrl = `https://${config.domain}/oauth/token`;
        this.issuer = `https://${config.domain}/`;
        this.jwks = createRemoteJWKSet(new URL(`https://${config.domain}/.well-known/jwks.json`));
    }

    get clientsStore() {
        return this._clientsStore;
    }

    getPendingAuthorization(pendingId: string): PendingAuthorization | undefined {
        return this.pendingAuthorizations.get(pendingId);
    }

    async authorize(client: OAuthClientInformationFull, params: AuthorizationParams, res: Response): Promise<void> {
        const pendingId = randomUUID();
        const scopes = params.scopes?.length ? params.scopes : this.defaultScopes;

        this.pendingAuthorizations.set(pendingId, {
            clientId: client.client_id,
            codeChallenge: params.codeChallenge,
            redirectUri: params.redirectUri,
            state: params.state,
            scopes
        });

        const auth0AuthorizeUrl = new URL(`https://${this.config.domain}/authorize`);
        auth0AuthorizeUrl.searchParams.set('response_type', 'code');
        auth0AuthorizeUrl.searchParams.set('client_id', this.config.clientId);
        auth0AuthorizeUrl.searchParams.set('redirect_uri', this.callbackUrl);
        auth0AuthorizeUrl.searchParams.set('audience', this.config.audience);
        auth0AuthorizeUrl.searchParams.set('scope', scopes.join(' '));
        auth0AuthorizeUrl.searchParams.set('state', pendingId);

        res.redirect(auth0AuthorizeUrl.toString());
    }

    completeAuthorizationFromPending(pendingId: string, auth0Tokens: OAuthTokens) {
        const pending = this.pendingAuthorizations.get(pendingId);
        if (!pending) {
            throw new InvalidGrantError('Unknown authorization state');
        }

        this.pendingAuthorizations.delete(pendingId);

        const mcpAuthCode = randomUUID();
        this.authorizationCodeGrants.set(mcpAuthCode, {
            clientId: pending.clientId,
            codeChallenge: pending.codeChallenge,
            redirectUri: pending.redirectUri,
            tokens: auth0Tokens
        });

        return {
            authorizationCode: mcpAuthCode,
            redirectUri: pending.redirectUri,
            originalState: pending.state
        };
    }

    async exchangeAuth0AuthorizationCode(code: string): Promise<OAuthTokens> {
        const params = new URLSearchParams();
        params.set('grant_type', 'authorization_code');
        params.set('client_id', this.config.clientId);
        params.set('client_secret', this.config.clientSecret);
        params.set('code', code);
        params.set('redirect_uri', this.callbackUrl);

        const response = await fetch(this.tokenUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: params.toString()
        });

        if (!response.ok) {
            throw new ServerError(`Auth0 authorization code exchange failed: ${response.status}`);
        }

        const data = await response.json();
        return OAuthTokensSchema.parse(data);
    }

    async challengeForAuthorizationCode(client: OAuthClientInformationFull, authorizationCode: string): Promise<string> {
        const grant = this.authorizationCodeGrants.get(authorizationCode);
        if (!grant || grant.clientId !== client.client_id) {
            throw new InvalidGrantError('Invalid authorization code');
        }

        return grant.codeChallenge;
    }

    async exchangeAuthorizationCode(
        client: OAuthClientInformationFull,
        authorizationCode: string,
        _codeVerifier?: string,
        redirectUri?: string
    ): Promise<OAuthTokens> {
        const grant = this.authorizationCodeGrants.get(authorizationCode);
        if (!grant || grant.clientId !== client.client_id) {
            throw new InvalidGrantError('Invalid authorization code');
        }

        if (redirectUri && redirectUri !== grant.redirectUri) {
            throw new InvalidGrantError('redirect_uri does not match authorization request');
        }

        this.authorizationCodeGrants.delete(authorizationCode);
        return grant.tokens;
    }

    async exchangeRefreshToken(
        _client: OAuthClientInformationFull,
        refreshToken: string,
        scopes?: string[]
    ): Promise<OAuthTokens> {
        const params = new URLSearchParams();
        params.set('grant_type', 'refresh_token');
        params.set('client_id', this.config.clientId);
        params.set('client_secret', this.config.clientSecret);
        params.set('refresh_token', refreshToken);

        if (scopes?.length) {
            params.set('scope', scopes.join(' '));
        }

        const response = await fetch(this.tokenUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: params.toString()
        });

        if (!response.ok) {
            throw new ServerError(`Auth0 refresh token exchange failed: ${response.status}`);
        }

        const data = await response.json();
        return OAuthTokensSchema.parse(data);
    }

    async verifyAccessToken(token: string): Promise<AuthInfo> {
        try {
            const { payload } = await jwtVerify(token, this.jwks, {
                issuer: this.issuer,
                audience: this.config.audience
            });

            const scopes = typeof payload.scope === 'string' ? payload.scope.split(' ').filter(Boolean) : [];
            const clientId = typeof payload.azp === 'string'
                ? payload.azp
                : typeof payload.client_id === 'string'
                    ? payload.client_id
                    : this.config.clientId;

            return {
                token,
                clientId,
                scopes,
                expiresAt: typeof payload.exp === 'number' ? payload.exp : undefined,
                extra: {
                    sub: payload.sub,
                    email: payload.email,
                    org_id: payload.org_id
                }
            };
        } catch (error) {
            throw new InvalidTokenError(
                `Invalid access token: ${error instanceof Error ? error.message : 'unknown verification error'}`
            );
        }
    }
}

export function readAuth0ProviderConfigFromEnv(env: NodeJS.ProcessEnv = process.env): Auth0ProviderConfig | null {
    const keys = [
        'AUTH0_DOMAIN',
        'AUTH0_CLIENT_ID',
        'AUTH0_CLIENT_SECRET',
        'AUTH0_AUDIENCE',
        'MCP_BASE_URL'
    ] as const;

    const values = keys.reduce((acc, key) => {
        acc[key] = env[key];
        return acc;
    }, {} as Record<(typeof keys)[number], string | undefined>);

    const present = keys.filter((key) => Boolean(values[key]));

    if (present.length === 0) {
        return null;
    }

    if (present.length !== keys.length) {
        const missing = keys.filter((key) => !values[key]);
        throw new Error(`Partial Auth0 OAuth configuration. Missing: ${missing.join(', ')}`);
    }

    return {
        domain: values.AUTH0_DOMAIN as string,
        clientId: values.AUTH0_CLIENT_ID as string,
        clientSecret: values.AUTH0_CLIENT_SECRET as string,
        audience: values.AUTH0_AUDIENCE as string,
        mcpBaseUrl: values.MCP_BASE_URL as string
    };
}
