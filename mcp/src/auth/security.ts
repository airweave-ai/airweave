import { createHash } from 'crypto';

const REDACTION = '[REDACTED]';

const SENSITIVE_KEYS = new Set([
    'authorization',
    'x-api-key',
    'api_key',
    'apikey',
    'access_token',
    'refresh_token',
    'client_secret',
    'code',
    'code_verifier',
]);

export function redactSensitiveValue(key: string, value: unknown): unknown {
    if (SENSITIVE_KEYS.has(key.toLowerCase())) {
        return REDACTION;
    }
    return value;
}

export function hashIdentifier(value: string): string {
    return createHash('sha256').update(value).digest('hex').slice(0, 16);
}

export function safeLogObject(obj: Record<string, unknown>): Record<string, unknown> {
    return Object.fromEntries(
        Object.entries(obj).map(([key, value]) => [key, redactSensitiveValue(key, value)])
    );
}
