import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mockPing = vi.fn().mockResolvedValue('PONG');
const mockConnect = vi.fn().mockResolvedValue(undefined);

let mockStatus = 'wait';

const MockRedisInstance = {
    ping: mockPing,
    connect: mockConnect,
    get status() { return mockStatus; },
};

vi.mock('ioredis', () => ({
    Redis: vi.fn(() => MockRedisInstance),
}));

describe('redis singleton', () => {
    const savedEnv: Record<string, string | undefined> = {};

    beforeEach(async () => {
        vi.clearAllMocks();
        mockStatus = 'wait';
        for (const key of ['MCP_REDIS_URL', 'REDIS_HOST', 'REDIS_PORT', 'REDIS_PASSWORD']) {
            savedEnv[key] = process.env[key];
            delete process.env[key];
        }
        vi.resetModules();
    });

    afterEach(() => {
        for (const [key, value] of Object.entries(savedEnv)) {
            if (value === undefined) delete process.env[key];
            else process.env[key] = value;
        }
    });

    async function loadModule() {
        return await import('../../src/auth/redis.js');
    }

    it('getRedisClient returns singleton across multiple calls', async () => {
        const { getRedisClient } = await loadModule();
        const a = getRedisClient();
        const b = getRedisClient();
        expect(a).toBe(b);
    });

    it('builds URL from REDIS_HOST / REDIS_PORT when no MCP_REDIS_URL', async () => {
        const { Redis } = await import('ioredis');
        process.env.REDIS_HOST = 'myhost';
        process.env.REDIS_PORT = '6380';
        const { getRedisClient } = await loadModule();
        getRedisClient();
        expect(Redis).toHaveBeenCalledWith('redis://myhost:6380/0', expect.any(Object));
    });

    it('includes password in URL when REDIS_PASSWORD is set', async () => {
        const { Redis } = await import('ioredis');
        process.env.REDIS_HOST = 'host';
        process.env.REDIS_PORT = '6379';
        process.env.REDIS_PASSWORD = 'p@ss';
        const { getRedisClient } = await loadModule();
        getRedisClient();
        expect(Redis).toHaveBeenCalledWith(
            `redis://:${encodeURIComponent('p@ss')}@host:6379/0`,
            expect.any(Object),
        );
    });

    it('prefers MCP_REDIS_URL over individual env vars', async () => {
        const { Redis } = await import('ioredis');
        process.env.MCP_REDIS_URL = 'redis://custom:1234/2';
        process.env.REDIS_HOST = 'ignored';
        const { getRedisClient } = await loadModule();
        getRedisClient();
        expect(Redis).toHaveBeenCalledWith('redis://custom:1234/2', expect.any(Object));
    });

    it('defaults to localhost:6379 when no env vars set', async () => {
        const { Redis } = await import('ioredis');
        const { getRedisClient } = await loadModule();
        getRedisClient();
        expect(Redis).toHaveBeenCalledWith('redis://localhost:6379/0', expect.any(Object));
    });

    describe('ensureRedisReady', () => {
        it('calls connect + ping when status is not ready', async () => {
            mockStatus = 'wait';
            const { ensureRedisReady, getRedisClient } = await loadModule();
            getRedisClient();
            await ensureRedisReady();
            expect(mockConnect).toHaveBeenCalledOnce();
            expect(mockPing).toHaveBeenCalledOnce();
        });

        it('skips connect when status is already ready', async () => {
            mockStatus = 'ready';
            const { ensureRedisReady, getRedisClient } = await loadModule();
            getRedisClient();
            await ensureRedisReady();
            expect(mockConnect).not.toHaveBeenCalled();
            expect(mockPing).not.toHaveBeenCalled();
        });
    });
});
