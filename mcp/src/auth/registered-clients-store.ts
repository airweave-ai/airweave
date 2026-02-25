import type { OAuthRegisteredClientsStore } from '@modelcontextprotocol/sdk/server/auth/clients.js';
import type { OAuthClientInformationFull } from '@modelcontextprotocol/sdk/shared/auth.js';
import { getRedisClient } from './redis.js';

const CLIENT_KEY_PREFIX = 'mcp:oauth:clients';
const CLIENT_TTL_SECONDS = parseInt(process.env.MCP_OAUTH_CLIENT_TTL_SECONDS || '604800', 10);

export class RedisRegisteredClientsStore implements OAuthRegisteredClientsStore {
    private key(clientId: string): string {
        return `${CLIENT_KEY_PREFIX}:${clientId}`;
    }

    async getClient(clientId: string): Promise<OAuthClientInformationFull | undefined> {
        const redis = getRedisClient();
        const raw = await redis.get(this.key(clientId));
        if (!raw) {
            return undefined;
        }
        return JSON.parse(raw) as OAuthClientInformationFull;
    }

    async registerClient(client: OAuthClientInformationFull): Promise<OAuthClientInformationFull> {
        const redis = getRedisClient();
        await redis.set(this.key(client.client_id), JSON.stringify(client), 'EX', CLIENT_TTL_SECONDS);
        return client;
    }
}
