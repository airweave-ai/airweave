import { describe, it, expect } from 'vitest';
import { parseCronExpression, formatTimeUntil } from './cronParser';

describe('parseCronExpression', () => {
  it('returns null for null/undefined/empty input', () => {
    expect(parseCronExpression(null)).toBeNull();
    expect(parseCronExpression(undefined)).toBeNull();
    expect(parseCronExpression('')).toBeNull();
  });

  it('returns null for invalid cron expressions', () => {
    expect(parseCronExpression('not a cron')).toBeNull();
    expect(parseCronExpression('* * *')).toBeNull();
    expect(parseCronExpression('* * * * * *')).toBeNull();
  });

  it('parses */5 * * * * as every 5 minutes', () => {
    const result = parseCronExpression('*/5 * * * *');
    expect(result).not.toBeNull();
    expect(result!.description.toLowerCase()).toContain('every 5 minutes');
  });

  it('parses */1 * * * * as every minute', () => {
    const result = parseCronExpression('*/1 * * * *');
    expect(result).not.toBeNull();
    expect(result!.description.toLowerCase()).toContain('every minute');
  });

  it('parses 0 * * * * as every hour', () => {
    const result = parseCronExpression('0 * * * *');
    expect(result).not.toBeNull();
    expect(result!.description.toLowerCase()).toContain('every hour');
  });

  it('parses 30 * * * * with :30', () => {
    const result = parseCronExpression('30 * * * *');
    expect(result).not.toBeNull();
    expect(result!.description).toMatch(/30 minutes/i);
  });

  it('parses 0 */2 * * * as every 2 hours', () => {
    const result = parseCronExpression('0 */2 * * *');
    expect(result).not.toBeNull();
    expect(result!.description.toLowerCase()).toContain('every 2 hours');
  });

  it('parses 30 14 * * * with 2:30 PM', () => {
    const result = parseCronExpression('30 14 * * *');
    expect(result).not.toBeNull();
    expect(result!.description).toContain('2:30 PM');
  });

  it('parses 0 9 * * 1 with Monday and 9:00', () => {
    const result = parseCronExpression('0 9 * * 1');
    expect(result).not.toBeNull();
    expect(result!.description).toMatch(/monday/i);
    expect(result!.description).toContain('9:00');
  });

  it('parses 0 0 1 * * for monthly schedule', () => {
    const result = parseCronExpression('0 0 1 * *');
    expect(result).not.toBeNull();
    expect(result!.description).toMatch(/1|12:00 AM|midnight/i);
  });

  it('all results have non-empty description properties', () => {
    const expressions = [
      '*/5 * * * *',
      '0 * * * *',
      '30 14 * * *',
      '0 9 * * 1',
      '0 0 1 * *',
    ];

    for (const expr of expressions) {
      const result = parseCronExpression(expr);
      expect(result).not.toBeNull();
      expect(result!.description.length).toBeGreaterThan(0);
      expect(result!.shortDescription.length).toBeGreaterThan(0);
      expect(result!.descriptionLocal.length).toBeGreaterThan(0);
      expect(result!.shortDescriptionLocal.length).toBeGreaterThan(0);
    }
  });
});

describe('formatTimeUntil', () => {
  it('returns empty string for null/undefined', () => {
    expect(formatTimeUntil(null)).toBe('');
    expect(formatTimeUntil(undefined)).toBe('');
  });

  it('returns "Now" for past dates', () => {
    const pastDate = new Date(Date.now() - 60000);
    expect(formatTimeUntil(pastDate)).toBe('Now');
  });

  it('returns a time string for future dates', () => {
    const futureDate = new Date(Date.now() + 3600000); // 1 hour from now
    const result = formatTimeUntil(futureDate);
    expect(result).toMatch(/^in \d+/);
  });

  it('handles string dates', () => {
    const futureDate = new Date(Date.now() + 7200000).toISOString(); // 2 hours
    const result = formatTimeUntil(futureDate);
    expect(result).toMatch(/^in \d+h/);
  });
});
