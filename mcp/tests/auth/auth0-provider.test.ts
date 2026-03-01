import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// --- Redis mock (shared by transaction store and registered clients store) ---
const redisStore = new Map<string, { value: string; ttl?: number }>();

vi.mock('../../src/auth/redis.js', () => ({
    getRedisClient: () => ({
        get: vi.fn(async (key: string) => redisStore.get(key)?.value ?? null),
        set: vi.fn(async (key: string, value: string, _ex?: string, ttl?: number) => {
            redisStore.set(key, { value, ttl });
            return 'OK';
        }),
        del: vi.fn(async (key: string) => {
            redisStore.delete(key);
            return 1;
        }),
        eval: vi.fn(async (_lua: string, _numKeys: number, key: string) => {
            const entry = redisStore.get(key);
            if (entry) {
                redisStore.delete(key);
                return entry.value;
            }
            return null;
        }),
    }),
}));

// --- jose mock ---
const mockJwtVerify = vi.fn();
const mockJwks = vi.fn();

vi.mock('jose', () => ({
    createRemoteJWKSet: (...args: unknown[]) => {
        mockJwks(...args);
        return 'mock-jwks';
    },
    jwtVerify: (...args: unknown[]) => mockJwtVerify(...args),
}));

// --- fetch mock ---
const mockFetch = vi.fn();
const originalFetch = globalThis.fetch;

import type { OAuthClientInformationFull } from '@modelcontextprotocol/sdk/shared/auth.js';

function fakeClient(overrides?: Partial<OAuthClientInformationFull>): OAuthClientInformationFull {
    return {
        client_id: 'test-client',
        client_name: 'Test',
        redirect_uris: ['https://example.com/callback'],
        grant_types: ['authorization_code'],
        response_types: ['code'],
        token_endpoint_auth_method: 'none',
        ...overrides,
    } as OAuthClientInformationFull;
}

describe('Auth0OAuthProvider', () => {
    const savedEnv: Record<string, string | undefined> = {};
    const envVars: Record<string, string> = {
        AUTH0_DOMAIN: 'test.auth0.com',
        AUTH0_CLIENT_ID: 'auth0-cid',
        AUTH0_CLIENT_SECRET: 'auth0-secret',
        AUTH0_AUDIENCE: 'https://api.test.com/',
        MCP_BASE_URL: 'https://mcp.test.com',
    };

    beforeEach(() => {
        vi.clearAllMocks();
        redisStore.clear();
        globalThis.fetch = mockFetch;
        for (const [key, value] of Object.entries(envVars)) {
            savedEnv[key] = process.env[key];
            process.env[key] = value;
        }
    });

    afterEach(() => {
        globalThis.fetch = originalFetch;
        for (const [key, value] of Object.entries(savedEnv)) {
            if (value === undefined) delete process.env[key];
            else process.env[key] = value;
        }
    });

    async function createProvider() {
        vi.resetModules();
        const mod = await import('../../src/auth/auth0-provider.js');
        return new mod.Auth0OAuthProvider();
    }

    describe('authorize', () => {
        it('redirects to Auth0 authorize endpoint with correct params', async () => {
            const provider = await createProvider();
            const client = fakeClient();
            let redirectUrl = '';
            const res = {
                redirect: vi.fn((_status: number, url: string) => { redirectUrl = url; }),
            } as any;

            await provider.authorize(client, {
                redirectUri: 'https://example.com/callback',
                codeChallenge: 'pkce-challenge',
                state: 'client-state',
                scopes: ['openid', 'profile'],
            }, res);

            expect(res.redirect).toHaveBeenCalledWith(302, expect.any(String));
            const url = new URL(redirectUrl);
            expect(url.hostname).toBe('test.auth0.com');
            expect(url.pathname).toBe('/authorize');
            expect(url.searchParams.get('response_type')).toBe('code');
            expect(url.searchParams.get('client_id')).toBe('auth0-cid');
            expect(url.searchParams.get('audience')).toBe('https://api.test.com/');
            expect(url.searchParams.get('redirect_uri')).toBe('https://mcp.test.com/oauth/callback');
            expect(url.searchParams.get('scope')).toBe('openid profile');
        });

        it('stores pending authorization in transaction store', async () => {
            const provider = await createProvider();
            const res = { redirect: vi.fn() } as any;
            await provider.authorize(fakeClient(), {
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                scopes: [],
            }, res);

            const pendingKeys = [...redisStore.keys()].filter(k => k.startsWith('mcp:oauth:pending:'));
            expect(pendingKeys).toHaveLength(1);
        });

        it('uses default scopes when none provided', async () => {
            const provider = await createProvider();
            let redirectUrl = '';
            const res = {
                redirect: vi.fn((_s: number, url: string) => { redirectUrl = url; }),
            } as any;

            await provider.authorize(fakeClient(), {
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
            }, res);

            const url = new URL(redirectUrl);
            expect(url.searchParams.get('scope')).toBe('openid profile email offline_access');
        });
    });

    describe('verifyAccessToken', () => {
        it('returns AuthInfo on valid JWT', async () => {
            mockJwtVerify.mockResolvedValue({
                payload: {
                    sub: 'auth0|user-123',
                    email: 'alice@example.com',
                    scope: 'openid profile',
                    exp: 9999999999,
                    azp: 'auth0-cid',
                },
            });

            const provider = await createProvider();
            const result = await provider.verifyAccessToken('valid-jwt-token');

            expect(result.token).toBe('valid-jwt-token');
            expect(result.scopes).toEqual(['openid', 'profile']);
            expect(result.expiresAt).toBe(9999999999);
            expect(result.clientId).toBe('auth0-cid');
            expect(result.extra?.sub).toBe('auth0|user-123');
            expect(result.extra?.email).toBe('alice@example.com');
        });

        it('passes correct issuer and audience to jwtVerify', async () => {
            mockJwtVerify.mockResolvedValue({
                payload: { sub: 'u', scope: '', azp: 'c' },
            });

            const provider = await createProvider();
            await provider.verifyAccessToken('tok');

            expect(mockJwtVerify).toHaveBeenCalledWith('tok', 'mock-jwks', {
                issuer: 'https://test.auth0.com/',
                audience: 'https://api.test.com/',
            });
        });

        it('propagates jwtVerify errors (expired / wrong audience)', async () => {
            mockJwtVerify.mockRejectedValue(new Error('JWT expired'));
            const provider = await createProvider();
            await expect(provider.verifyAccessToken('expired-tok')).rejects.toThrow('JWT expired');
        });

        it('handles missing scope gracefully', async () => {
            mockJwtVerify.mockResolvedValue({
                payload: { sub: 'u', azp: 'c' },
            });
            const provider = await createProvider();
            const result = await provider.verifyAccessToken('tok');
            expect(result.scopes).toEqual([]);
        });

        it('falls back to client_id when azp is absent', async () => {
            mockJwtVerify.mockResolvedValue({
                payload: { sub: 'u', client_id: 'fallback-cid' },
            });
            const provider = await createProvider();
            const result = await provider.verifyAccessToken('tok');
            expect(result.clientId).toBe('fallback-cid');
        });

        it('falls back to "auth0" when neither azp nor client_id present', async () => {
            mockJwtVerify.mockResolvedValue({
                payload: { sub: 'u' },
            });
            const provider = await createProvider();
            const result = await provider.verifyAccessToken('tok');
            expect(result.clientId).toBe('auth0');
        });
    });

    describe('challengeForAuthorizationCode', () => {
        it('returns code challenge for valid authorization code', async () => {
            const provider = await createProvider();
            const client = fakeClient();

            const res = { redirect: vi.fn() } as any;
            await provider.authorize(client, {
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'my-challenge',
                scopes: [],
            }, res);

            // Simulate the callback flow: exchange Auth0 code for local code
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    access_token: 'at',
                    token_type: 'Bearer',
                    expires_in: 3600,
                }),
            });

            const stateId = res.redirect.mock.calls[0][1].match(/state=([^&]+)/)?.[1];
            const { code } = await provider.exchangeAuth0CodeForLocalCode(stateId!, 'auth0-code');

            const challenge = await provider.challengeForAuthorizationCode(client, code);
            expect(challenge).toBe('my-challenge');
        });

        it('throws on invalid authorization code', async () => {
            const provider = await createProvider();
            await expect(
                provider.challengeForAuthorizationCode(fakeClient(), 'nonexistent')
            ).rejects.toThrow('Invalid authorization code');
        });

        it('throws when client_id does not match', async () => {
            const provider = await createProvider();
            const client = fakeClient({ client_id: 'client-a' });

            const res = { redirect: vi.fn() } as any;
            await provider.authorize(client, {
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                scopes: [],
            }, res);

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ access_token: 'at', token_type: 'Bearer' }),
            });

            const stateId = res.redirect.mock.calls[0][1].match(/state=([^&]+)/)?.[1];
            const { code } = await provider.exchangeAuth0CodeForLocalCode(stateId!, 'auth0-code');

            const otherClient = fakeClient({ client_id: 'client-b' });
            await expect(
                provider.challengeForAuthorizationCode(otherClient, code)
            ).rejects.toThrow('Invalid authorization code');
        });
    });

    describe('exchangeAuthorizationCode', () => {
        it('returns tokens for valid code', async () => {
            const provider = await createProvider();
            const client = fakeClient();
            const res = { redirect: vi.fn() } as any;

            await provider.authorize(client, {
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                scopes: [],
            }, res);

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    access_token: 'at-final',
                    refresh_token: 'rt-final',
                    token_type: 'Bearer',
                    expires_in: 3600,
                }),
            });

            const stateId = res.redirect.mock.calls[0][1].match(/state=([^&]+)/)?.[1];
            const { code } = await provider.exchangeAuth0CodeForLocalCode(stateId!, 'auth0-code');

            const tokens = await provider.exchangeAuthorizationCode(client, code, undefined, 'https://example.com/cb');
            expect(tokens.access_token).toBe('at-final');
            expect(tokens.refresh_token).toBe('rt-final');
            expect(tokens.token_type).toBe('Bearer');
        });

        it('rejects consumed code (one-time use)', async () => {
            const provider = await createProvider();
            const client = fakeClient();
            const res = { redirect: vi.fn() } as any;

            await provider.authorize(client, {
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                scopes: [],
            }, res);

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ access_token: 'at', token_type: 'Bearer' }),
            });

            const stateId = res.redirect.mock.calls[0][1].match(/state=([^&]+)/)?.[1];
            const { code } = await provider.exchangeAuth0CodeForLocalCode(stateId!, 'auth0-code');

            await provider.exchangeAuthorizationCode(client, code);
            await expect(
                provider.exchangeAuthorizationCode(client, code)
            ).rejects.toThrow('Invalid or expired authorization code');
        });

        it('rejects mismatched redirect_uri', async () => {
            const provider = await createProvider();
            const client = fakeClient();
            const res = { redirect: vi.fn() } as any;

            await provider.authorize(client, {
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                scopes: [],
            }, res);

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ access_token: 'at', token_type: 'Bearer' }),
            });

            const stateId = res.redirect.mock.calls[0][1].match(/state=([^&]+)/)?.[1];
            const { code } = await provider.exchangeAuth0CodeForLocalCode(stateId!, 'auth0-code');

            await expect(
                provider.exchangeAuthorizationCode(client, code, undefined, 'https://evil.com/cb')
            ).rejects.toThrow('Redirect URI mismatch');
        });
    });

    describe('exchangeRefreshToken', () => {
        it('calls Auth0 token endpoint with correct body', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    access_token: 'new-at',
                    token_type: 'Bearer',
                    expires_in: 3600,
                }),
            });

            const provider = await createProvider();
            const tokens = await provider.exchangeRefreshToken(fakeClient(), 'rt-123', ['openid']);

            expect(tokens.access_token).toBe('new-at');
            expect(mockFetch).toHaveBeenCalledOnce();
            const [url, opts] = mockFetch.mock.calls[0];
            expect(url.toString()).toContain('test.auth0.com/oauth/token');
            const body = JSON.parse(opts.body);
            expect(body.grant_type).toBe('refresh_token');
            expect(body.refresh_token).toBe('rt-123');
            expect(body.client_id).toBe('auth0-cid');
            expect(body.client_secret).toBe('auth0-secret');
            expect(body.scope).toBe('openid');
        });

        it('throws on non-OK response', async () => {
            mockFetch.mockResolvedValueOnce({ ok: false, status: 403 });
            const provider = await createProvider();
            await expect(
                provider.exchangeRefreshToken(fakeClient(), 'bad-rt')
            ).rejects.toThrow('Auth0 refresh failed with status 403');
        });
    });

    describe('revokeToken', () => {
        it('calls Auth0 revoke endpoint', async () => {
            mockFetch.mockResolvedValueOnce({ ok: true });
            const provider = await createProvider();
            await provider.revokeToken(fakeClient(), { token: 'rt-to-revoke', token_type_hint: 'refresh_token' });

            expect(mockFetch).toHaveBeenCalledOnce();
            const [url, opts] = mockFetch.mock.calls[0];
            expect(url.toString()).toContain('test.auth0.com/oauth/revoke');
            const body = JSON.parse(opts.body);
            expect(body.token).toBe('rt-to-revoke');
            expect(body.client_id).toBe('auth0-cid');
        });

        it('(Concern #6) silently ignores non-OK response from Auth0', async () => {
            mockFetch.mockResolvedValueOnce({ ok: false, status: 500 });
            const provider = await createProvider();
            // Current implementation does not check response — this should NOT throw.
            // When the bug is fixed, change this to: rejects.toThrow()
            await expect(
                provider.revokeToken(fakeClient(), { token: 'tok', token_type_hint: 'refresh_token' })
            ).resolves.toBeUndefined();
        });
    });

    describe('exchangeAuth0CodeForLocalCode', () => {
        it('exchanges Auth0 code and returns local code + redirect info', async () => {
            const provider = await createProvider();
            const client = fakeClient();
            const res = { redirect: vi.fn() } as any;

            await provider.authorize(client, {
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                state: 'original-state',
                scopes: ['openid'],
            }, res);

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    access_token: 'at',
                    refresh_token: 'rt',
                    token_type: 'Bearer',
                    expires_in: 3600,
                }),
            });

            const stateId = res.redirect.mock.calls[0][1].match(/state=([^&]+)/)?.[1];
            const result = await provider.exchangeAuth0CodeForLocalCode(stateId!, 'auth0-code');

            expect(result.code).toBeDefined();
            expect(result.redirectUri).toBe('https://example.com/cb');
            expect(result.state).toBe('original-state');
        });

        it('(Concern #9) returns tokens field (unused by callback handler)', async () => {
            const provider = await createProvider();
            const res = { redirect: vi.fn() } as any;

            await provider.authorize(fakeClient(), {
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                scopes: [],
            }, res);

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    access_token: 'at',
                    token_type: 'Bearer',
                }),
            });

            const stateId = res.redirect.mock.calls[0][1].match(/state=([^&]+)/)?.[1];
            const result = await provider.exchangeAuth0CodeForLocalCode(stateId!, 'code');
            expect(result.tokens).toBeDefined();
            expect(result.tokens.access_token).toBe('at');
        });

        it('throws on invalid/expired state', async () => {
            const provider = await createProvider();
            await expect(
                provider.exchangeAuth0CodeForLocalCode('nonexistent-state', 'code')
            ).rejects.toThrow('Invalid or expired OAuth state');
        });

        it('throws when Auth0 token exchange fails', async () => {
            const provider = await createProvider();
            const res = { redirect: vi.fn() } as any;

            await provider.authorize(fakeClient(), {
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                scopes: [],
            }, res);

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                text: async () => 'invalid_grant',
            });

            const stateId = res.redirect.mock.calls[0][1].match(/state=([^&]+)/)?.[1];
            await expect(
                provider.exchangeAuth0CodeForLocalCode(stateId!, 'bad-code')
            ).rejects.toThrow('Auth0 code exchange failed with status 400');
        });

        it('cleans up pending authorization after successful exchange', async () => {
            const provider = await createProvider();
            const res = { redirect: vi.fn() } as any;

            await provider.authorize(fakeClient(), {
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                scopes: [],
            }, res);

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ access_token: 'at', token_type: 'Bearer' }),
            });

            const stateId = res.redirect.mock.calls[0][1].match(/state=([^&]+)/)?.[1];
            await provider.exchangeAuth0CodeForLocalCode(stateId!, 'code');

            const pendingKeys = [...redisStore.keys()].filter(k => k.startsWith('mcp:oauth:pending:'));
            expect(pendingKeys).toHaveLength(0);
        });
    });
});
