import { describe, it, expect, vi, beforeEach } from 'vitest';

const store = new Map<string, { value: string; ttl?: number }>();

vi.mock('../../src/auth/redis.js', () => ({
    getRedisClient: () => ({
        get: vi.fn(async (key: string) => store.get(key)?.value ?? null),
        set: vi.fn(async (key: string, value: string, _ex?: string, ttl?: number) => {
            store.set(key, { value, ttl });
            return 'OK';
        }),
        del: vi.fn(async (key: string) => {
            const had = store.has(key);
            store.delete(key);
            return had ? 1 : 0;
        }),
        eval: vi.fn(async (_lua: string, _numKeys: number, key: string) => {
            const entry = store.get(key);
            if (entry) {
                store.delete(key);
                return entry.value;
            }
            return null;
        }),
    }),
}));

import { OAuthTransactionStore } from '../../src/auth/oauth-transaction-store.js';

describe('OAuthTransactionStore', () => {
    let txStore: OAuthTransactionStore;

    beforeEach(() => {
        store.clear();
        txStore = new OAuthTransactionStore();
    });

    const pendingInput = {
        clientId: 'client-1',
        redirectUri: 'https://example.com/callback',
        codeChallenge: 'challenge-abc',
        state: 'state-xyz',
        scopes: ['openid', 'profile'],
    };

    describe('createPendingAuthorization', () => {
        it('returns record with generated id and createdAt', async () => {
            const result = await txStore.createPendingAuthorization(pendingInput);
            expect(result.id).toBeDefined();
            expect(result.id).toMatch(/^[0-9a-f-]{36}$/);
            expect(result.createdAt).toBeGreaterThan(0);
            expect(result.clientId).toBe('client-1');
            expect(result.redirectUri).toBe('https://example.com/callback');
        });

        it('stores record in Redis with correct TTL', async () => {
            const result = await txStore.createPendingAuthorization(pendingInput);
            const key = `mcp:oauth:pending:${result.id}`;
            const entry = store.get(key);
            expect(entry).toBeDefined();
            expect(entry!.ttl).toBe(600);
        });
    });

    describe('getPendingAuthorization', () => {
        it('returns stored record', async () => {
            const created = await txStore.createPendingAuthorization(pendingInput);
            const fetched = await txStore.getPendingAuthorization(created.id);
            expect(fetched).toBeDefined();
            expect(fetched!.clientId).toBe('client-1');
            expect(fetched!.state).toBe('state-xyz');
        });

        it('returns undefined for missing id', async () => {
            const result = await txStore.getPendingAuthorization('nonexistent');
            expect(result).toBeUndefined();
        });
    });

    describe('deletePendingAuthorization', () => {
        it('removes the record from storage', async () => {
            const created = await txStore.createPendingAuthorization(pendingInput);
            await txStore.deletePendingAuthorization(created.id);
            const fetched = await txStore.getPendingAuthorization(created.id);
            expect(fetched).toBeUndefined();
        });
    });

    describe('issueAuthorizationCode', () => {
        const codeInput = {
            clientId: 'client-1',
            redirectUri: 'https://example.com/callback',
            codeChallenge: 'challenge-abc',
            tokens: {
                access_token: 'at-123',
                refresh_token: 'rt-456',
                token_type: 'Bearer',
                expires_in: 3600,
            },
            scopes: ['openid'],
        };

        it('returns record with generated id', async () => {
            const result = await txStore.issueAuthorizationCode(codeInput);
            expect(result.id).toMatch(/^[0-9a-f-]{36}$/);
            expect(result.tokens.access_token).toBe('at-123');
        });

        it('stores with CODE_TTL_SECONDS (default 60)', async () => {
            const result = await txStore.issueAuthorizationCode(codeInput);
            const key = `mcp:oauth:code:${result.id}`;
            const entry = store.get(key);
            expect(entry!.ttl).toBe(60);
        });
    });

    describe('consumeAuthorizationCode', () => {
        it('returns the record and deletes it atomically', async () => {
            const issued = await txStore.issueAuthorizationCode({
                clientId: 'c1',
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                tokens: { access_token: 'tok' },
                scopes: [],
            });

            const consumed = await txStore.consumeAuthorizationCode(issued.id);
            expect(consumed).toBeDefined();
            expect(consumed!.tokens.access_token).toBe('tok');

            const key = `mcp:oauth:code:${issued.id}`;
            expect(store.has(key)).toBe(false);
        });

        it('returns undefined on second call (one-time use)', async () => {
            const issued = await txStore.issueAuthorizationCode({
                clientId: 'c1',
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                tokens: { access_token: 'tok' },
                scopes: [],
            });

            await txStore.consumeAuthorizationCode(issued.id);
            const second = await txStore.consumeAuthorizationCode(issued.id);
            expect(second).toBeUndefined();
        });

        it('returns undefined for nonexistent code', async () => {
            const result = await txStore.consumeAuthorizationCode('no-such-code');
            expect(result).toBeUndefined();
        });
    });

    describe('getAuthorizationCode', () => {
        it('returns code record without consuming it', async () => {
            const issued = await txStore.issueAuthorizationCode({
                clientId: 'c1',
                redirectUri: 'https://example.com/cb',
                codeChallenge: 'ch',
                tokens: { access_token: 'tok' },
                scopes: [],
            });

            const first = await txStore.getAuthorizationCode(issued.id);
            const second = await txStore.getAuthorizationCode(issued.id);
            expect(first).toBeDefined();
            expect(second).toBeDefined();
            expect(first!.id).toBe(second!.id);
        });
    });
});
