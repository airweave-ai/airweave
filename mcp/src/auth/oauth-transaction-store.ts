import { randomUUID } from 'crypto';
import { getRedisClient } from './redis.js';

export type PendingAuthorization = {
    id: string;
    clientId: string;
    redirectUri: string;
    codeChallenge: string;
    state?: string;
    scopes: string[];
    createdAt: number;
};

export type AuthorizationCodeRecord = {
    id: string;
    clientId: string;
    redirectUri: string;
    codeChallenge: string;
    tokens: {
        access_token: string;
        refresh_token?: string;
        token_type?: string;
        expires_in?: number;
        scope?: string;
    };
    scopes: string[];
    createdAt: number;
};

const KEY_PREFIX = 'mcp:oauth';
const PENDING_TTL_SECONDS = parseInt(process.env.MCP_OAUTH_PENDING_TTL_SECONDS || '600', 10);
const CODE_TTL_SECONDS = parseInt(process.env.MCP_OAUTH_CODE_TTL_SECONDS || '60', 10);

export class OAuthTransactionStore {
    private keyPending(id: string): string {
        return `${KEY_PREFIX}:pending:${id}`;
    }

    private keyCode(id: string): string {
        return `${KEY_PREFIX}:code:${id}`;
    }

    async createPendingAuthorization(input: Omit<PendingAuthorization, 'id' | 'createdAt'>): Promise<PendingAuthorization> {
        const pending: PendingAuthorization = {
            ...input,
            id: randomUUID(),
            createdAt: Date.now(),
        };

        const redis = getRedisClient();
        await redis.set(
            this.keyPending(pending.id),
            JSON.stringify(pending),
            'EX',
            PENDING_TTL_SECONDS
        );

        return pending;
    }

    async getPendingAuthorization(id: string): Promise<PendingAuthorization | undefined> {
        const redis = getRedisClient();
        const raw = await redis.get(this.keyPending(id));
        if (!raw) {
            return undefined;
        }
        return JSON.parse(raw) as PendingAuthorization;
    }

    async deletePendingAuthorization(id: string): Promise<void> {
        const redis = getRedisClient();
        await redis.del(this.keyPending(id));
    }

    async issueAuthorizationCode(input: Omit<AuthorizationCodeRecord, 'id' | 'createdAt'>): Promise<AuthorizationCodeRecord> {
        const record: AuthorizationCodeRecord = {
            ...input,
            id: randomUUID(),
            createdAt: Date.now(),
        };

        const redis = getRedisClient();
        await redis.set(this.keyCode(record.id), JSON.stringify(record), 'EX', CODE_TTL_SECONDS);
        return record;
    }

    async getAuthorizationCode(id: string): Promise<AuthorizationCodeRecord | undefined> {
        const redis = getRedisClient();
        const raw = await redis.get(this.keyCode(id));
        if (!raw) {
            return undefined;
        }
        return JSON.parse(raw) as AuthorizationCodeRecord;
    }

    async consumeAuthorizationCode(id: string): Promise<AuthorizationCodeRecord | undefined> {
        const redis = getRedisClient();
        const key = this.keyCode(id);

        // Atomically get and delete to enforce one-time authorization code usage.
        const lua = `
            local value = redis.call("GET", KEYS[1])
            if value then
                redis.call("DEL", KEYS[1])
            end
            return value
        `;
        const raw = await redis.eval(lua, 1, key);
        if (!raw || typeof raw !== 'string') {
            return undefined;
        }

        return JSON.parse(raw) as AuthorizationCodeRecord;
    }
}
