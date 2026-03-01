import { describe, it, expect, vi, beforeEach } from 'vitest';
import express from 'express';
import request from 'supertest';
import { createAuth0CallbackHandler } from '../../src/auth/auth0-callback.js';

function createApp(provider: any): express.Application {
    const app = express();
    app.get('/oauth/callback', createAuth0CallbackHandler(provider));
    return app;
}

describe('auth0 callback handler', () => {
    let mockProvider: any;

    beforeEach(() => {
        vi.clearAllMocks();
        mockProvider = {
            exchangeAuth0CodeForLocalCode: vi.fn(),
        };
    });

    it('returns 400 when state is missing', async () => {
        const app = createApp(mockProvider);
        const res = await request(app).get('/oauth/callback?code=abc');
        expect(res.status).toBe(400);
        expect(res.body.error).toBe('missing state or code');
    });

    it('returns 400 when code is missing', async () => {
        const app = createApp(mockProvider);
        const res = await request(app).get('/oauth/callback?state=xyz');
        expect(res.status).toBe(400);
        expect(res.body.error).toBe('missing state or code');
    });

    it('returns 400 when both state and code are missing', async () => {
        const app = createApp(mockProvider);
        const res = await request(app).get('/oauth/callback');
        expect(res.status).toBe(400);
        expect(res.body.error).toBe('missing state or code');
    });

    it('redirects to client redirect_uri with code and state on success', async () => {
        mockProvider.exchangeAuth0CodeForLocalCode.mockResolvedValue({
            code: 'local-code-123',
            redirectUri: 'https://client.example.com/callback',
            state: 'client-state-abc',
            tokens: { access_token: 'should-not-appear' },
        });

        const app = createApp(mockProvider);
        const res = await request(app)
            .get('/oauth/callback?state=pending-id&code=auth0-code')
            .redirects(0);

        expect(res.status).toBe(302);
        const location = new URL(res.headers.location);
        expect(location.origin + location.pathname).toBe('https://client.example.com/callback');
        expect(location.searchParams.get('code')).toBe('local-code-123');
        expect(location.searchParams.get('state')).toBe('client-state-abc');
    });

    it('(Concern #9) redirect URL does not contain token data', async () => {
        mockProvider.exchangeAuth0CodeForLocalCode.mockResolvedValue({
            code: 'local-code',
            redirectUri: 'https://client.example.com/callback',
            state: 'st',
            tokens: { access_token: 'secret-at', refresh_token: 'secret-rt' },
        });

        const app = createApp(mockProvider);
        const res = await request(app)
            .get('/oauth/callback?state=s&code=c')
            .redirects(0);

        const location = res.headers.location;
        expect(location).not.toContain('secret-at');
        expect(location).not.toContain('secret-rt');
        expect(location).not.toContain('access_token');
        expect(location).not.toContain('refresh_token');
    });

    it('omits state param in redirect when state is undefined', async () => {
        mockProvider.exchangeAuth0CodeForLocalCode.mockResolvedValue({
            code: 'local-code',
            redirectUri: 'https://client.example.com/callback',
            state: undefined,
            tokens: {},
        });

        const app = createApp(mockProvider);
        const res = await request(app)
            .get('/oauth/callback?state=s&code=c')
            .redirects(0);

        const location = new URL(res.headers.location);
        expect(location.searchParams.has('state')).toBe(false);
    });

    it('returns 400 with generic error on provider failure (no sensitive data leaked)', async () => {
        mockProvider.exchangeAuth0CodeForLocalCode.mockRejectedValue(
            new Error('Auth0 code exchange failed with status 400: invalid_grant')
        );

        const app = createApp(mockProvider);
        const res = await request(app).get('/oauth/callback?state=s&code=c');
        expect(res.status).toBe(400);
        expect(res.body.error).toBe('oauth_callback_failed');
        expect(JSON.stringify(res.body)).not.toContain('invalid_grant');
        expect(JSON.stringify(res.body)).not.toContain('Auth0');
    });
});
