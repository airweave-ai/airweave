import { describe, it, expect } from 'vitest';
import { redactSensitiveValue, hashIdentifier, safeLogObject } from '../../src/auth/security.js';

describe('security utilities', () => {
    describe('redactSensitiveValue', () => {
        const sensitiveKeys = [
            'authorization',
            'x-api-key',
            'api_key',
            'apikey',
            'access_token',
            'refresh_token',
            'client_secret',
            'code',
            'code_verifier',
        ];

        it.each(sensitiveKeys)('redacts value for sensitive key "%s"', (key) => {
            expect(redactSensitiveValue(key, 'secret-value')).toBe('[REDACTED]');
        });

        it('is case-insensitive for sensitive keys', () => {
            expect(redactSensitiveValue('Authorization', 'Bearer xyz')).toBe('[REDACTED]');
            expect(redactSensitiveValue('ACCESS_TOKEN', 'tok')).toBe('[REDACTED]');
        });

        it('passes through non-sensitive keys unchanged', () => {
            expect(redactSensitiveValue('username', 'alice')).toBe('alice');
            expect(redactSensitiveValue('collection', 'my-col')).toBe('my-col');
            expect(redactSensitiveValue('method', 'POST')).toBe('POST');
        });

        it('passes through non-string values for non-sensitive keys', () => {
            expect(redactSensitiveValue('count', 42)).toBe(42);
            expect(redactSensitiveValue('enabled', true)).toBe(true);
            expect(redactSensitiveValue('data', null)).toBe(null);
        });
    });

    describe('hashIdentifier', () => {
        it('returns a deterministic 16-char hex string', () => {
            const hash = hashIdentifier('test-input');
            expect(hash).toHaveLength(16);
            expect(hash).toMatch(/^[0-9a-f]{16}$/);
            expect(hashIdentifier('test-input')).toBe(hash);
        });

        it('produces different hashes for different inputs', () => {
            expect(hashIdentifier('input-a')).not.toBe(hashIdentifier('input-b'));
        });
    });

    describe('safeLogObject', () => {
        it('redacts all sensitive keys in an object', () => {
            const input = {
                authorization: 'Bearer secret',
                client_secret: 'shh',
                username: 'alice',
                method: 'POST',
            };
            const result = safeLogObject(input);
            expect(result.authorization).toBe('[REDACTED]');
            expect(result.client_secret).toBe('[REDACTED]');
            expect(result.username).toBe('alice');
            expect(result.method).toBe('POST');
        });

        it('returns a new object (does not mutate input)', () => {
            const input = { code: 'abc123', safe: 'ok' };
            const result = safeLogObject(input);
            expect(result).not.toBe(input);
            expect(input.code).toBe('abc123');
        });
    });
});
