import { Redis } from 'ioredis';

let client: Redis | null = null;

function getRedisUrl(): string {
    const redisUrl = process.env.MCP_REDIS_URL;
    if (redisUrl) {
        return redisUrl;
    }

    const host = process.env.REDIS_HOST || 'localhost';
    const port = process.env.REDIS_PORT || '6379';
    const password = process.env.REDIS_PASSWORD;

    if (password) {
        return `redis://:${encodeURIComponent(password)}@${host}:${port}/0`;
    }

    return `redis://${host}:${port}/0`;
}

export function getRedisClient(): Redis {
    if (!client) {
        client = new Redis(getRedisUrl(), {
            lazyConnect: true,
            maxRetriesPerRequest: 2,
            enableOfflineQueue: false,
        });
    }
    return client as Redis;
}

export async function ensureRedisReady(): Promise<void> {
    const redis = getRedisClient();
    if (redis.status === 'ready') {
        return;
    }

    await redis.connect();
    await redis.ping();
}
