import { describe, it, expect, vi } from 'vitest';
import { Request, Response } from 'express';
import { OAuthClientInformationFull, OAuthTokens } from '@modelcontextprotocol/sdk/shared/auth.js';
import { InMemoryClientsStore } from '../src/auth/clients-store.js';
import { Auth0OAuthServerProvider } from '../src/auth/auth0-provider.js';
import { createAuth0CallbackHandler } from '../src/auth/auth0-callback.js';

function createTestClient(): OAuthClientInformationFull {
    return {
        client_id: 'test-client-id',
        redirect_uris: ['https://agent-builder.example.com/callback'],
        grant_types: ['authorization_code', 'refresh_token'],
        response_types: ['code'],
        token_endpoint_auth_method: 'client_secret_post'
    };
}

describe('Auth0 OAuth integration pieces', () => {
    it('registers and fetches dynamic clients in memory', () => {
        const store = new InMemoryClientsStore();
        const client = createTestClient();

        store.registerClient(client);
        expect(store.getClient(client.client_id)).toEqual(client);
    });

    it('builds Auth0 authorize redirect and exchanges stored MCP auth code', async () => {
        const provider = new Auth0OAuthServerProvider({
            domain: 'airweave.us.auth0.com',
            clientId: 'auth0-client-id',
            clientSecret: 'auth0-client-secret',
            audience: 'https://api.airweave.ai',
            mcpBaseUrl: 'https://mcp.airweave.ai'
        });

        const client = createTestClient();
        const redirect = vi.fn();
        const res = { redirect } as unknown as Response;

        await provider.authorize(client, {
            codeChallenge: 'pkce-code-challenge',
            redirectUri: 'https://agent-builder.example.com/callback',
            state: 'original-client-state',
            scopes: ['openid', 'profile', 'email']
        }, res);

        expect(redirect).toHaveBeenCalledTimes(1);
        const authUrl = new URL(redirect.mock.calls[0][0]);
        const pendingId = authUrl.searchParams.get('state');
        expect(pendingId).toBeTruthy();
        expect(provider.getPendingAuthorization(pendingId as string)).toBeTruthy();

        const tokens: OAuthTokens = {
            access_token: 'auth0-access-token',
            token_type: 'Bearer',
            refresh_token: 'auth0-refresh-token',
            expires_in: 3600
        };

        const completed = provider.completeAuthorizationFromPending(pendingId as string, tokens);
        expect(completed.redirectUri).toBe('https://agent-builder.example.com/callback');
        expect(completed.originalState).toBe('original-client-state');

        const challenge = await provider.challengeForAuthorizationCode(client, completed.authorizationCode);
        expect(challenge).toBe('pkce-code-challenge');

        const exchanged = await provider.exchangeAuthorizationCode(
            client,
            completed.authorizationCode,
            undefined,
            'https://agent-builder.example.com/callback'
        );
        expect(exchanged).toEqual(tokens);
    });

    it('redirects Auth0 callback back to MCP client with generated code', async () => {
        const provider = {
            getPendingAuthorization: vi.fn().mockReturnValue({
                redirectUri: 'https://agent-builder.example.com/callback',
                state: 'client-state-123'
            }),
            exchangeAuth0AuthorizationCode: vi.fn().mockResolvedValue({
                access_token: 'auth0-access-token',
                token_type: 'Bearer',
                refresh_token: 'auth0-refresh-token',
                expires_in: 3600
            } satisfies OAuthTokens),
            completeAuthorizationFromPending: vi.fn().mockReturnValue({
                authorizationCode: 'mcp-auth-code-abc',
                redirectUri: 'https://agent-builder.example.com/callback',
                originalState: 'client-state-123'
            })
        };
        const handler = createAuth0CallbackHandler(provider);
        const req = {
            query: {
                code: 'auth0-code-xyz',
                state: 'pending-id-1'
            }
        } as unknown as Request;
        const res = {
            redirect: vi.fn(),
            status: vi.fn().mockReturnThis(),
            json: vi.fn()
        } as unknown as Response;

        await handler(req, res);

        expect(res.redirect).toHaveBeenCalledTimes(1);
        const redirect = new URL((res.redirect as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]);
        expect(redirect.searchParams.get('code')).toBe('mcp-auth-code-abc');
        expect(redirect.searchParams.get('state')).toBe('client-state-123');
    });
});
