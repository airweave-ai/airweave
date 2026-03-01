import { describe, it, expect, vi, beforeEach } from 'vitest';

const store = new Map<string, { value: string; ttl?: number }>();

vi.mock('../../src/auth/redis.js', () => ({
    getRedisClient: () => ({
        get: vi.fn(async (key: string) => store.get(key)?.value ?? null),
        set: vi.fn(async (key: string, value: string, _ex?: string, ttl?: number) => {
            store.set(key, { value, ttl });
            return 'OK';
        }),
    }),
}));

import { RedisRegisteredClientsStore } from '../../src/auth/registered-clients-store.js';
import type { OAuthClientInformationFull } from '@modelcontextprotocol/sdk/shared/auth.js';

function fakeClient(overrides?: Partial<OAuthClientInformationFull>): OAuthClientInformationFull {
    return {
        client_id: 'test-client-id',
        client_name: 'Test Client',
        redirect_uris: ['https://example.com/callback'],
        grant_types: ['authorization_code'],
        response_types: ['code'],
        token_endpoint_auth_method: 'none',
        ...overrides,
    } as OAuthClientInformationFull;
}

describe('RedisRegisteredClientsStore', () => {
    let clientsStore: RedisRegisteredClientsStore;

    beforeEach(() => {
        store.clear();
        clientsStore = new RedisRegisteredClientsStore();
    });

    describe('registerClient', () => {
        it('stores client and returns it', async () => {
            const client = fakeClient();
            const result = await clientsStore.registerClient(client);
            expect(result).toEqual(client);
        });

        it('stores with 7-day TTL by default', async () => {
            const client = fakeClient({ client_id: 'c-ttl' });
            await clientsStore.registerClient(client);
            const entry = store.get('mcp:oauth:clients:c-ttl');
            expect(entry).toBeDefined();
            expect(entry!.ttl).toBe(604800);
        });

        it('stores serialized JSON', async () => {
            const client = fakeClient({ client_id: 'c-json' });
            await clientsStore.registerClient(client);
            const entry = store.get('mcp:oauth:clients:c-json');
            expect(JSON.parse(entry!.value)).toEqual(client);
        });
    });

    describe('getClient', () => {
        it('returns stored client', async () => {
            const client = fakeClient({ client_id: 'c-get' });
            await clientsStore.registerClient(client);
            const result = await clientsStore.getClient('c-get');
            expect(result).toEqual(client);
        });

        it('returns undefined for unknown client', async () => {
            const result = await clientsStore.getClient('nonexistent');
            expect(result).toBeUndefined();
        });

        it('(Concern #7) returns undefined after TTL expiry (simulated)', async () => {
            const client = fakeClient({ client_id: 'c-expiry' });
            await clientsStore.registerClient(client);
            store.delete('mcp:oauth:clients:c-expiry');
            const result = await clientsStore.getClient('c-expiry');
            expect(result).toBeUndefined();
        });
    });
});
