import { describe, expect, it } from "vitest";

import { formatDate, formatRelativeDate, getDaysFromNow } from "../date";

describe("formatDate", () => {
  it("formats date in short style by default", () => {
    const result = formatDate("2024-01-15T10:30:00Z");
    expect(result).toMatch(/Jan\s+15,\s+2024/);
  });

  it("formats date in long style", () => {
    const result = formatDate("2024-01-15T10:30:00Z", "long");
    expect(result).toMatch(/January\s+15,\s+2024/);
  });

  it("formats date with time in datetime style", () => {
    const result = formatDate("2024-01-15T10:30:00Z", "datetime");
    expect(result).toContain("2024");
    expect(result).toContain("January");
  });

  it("returns original string for invalid date", () => {
    const result = formatDate("not-a-date");
    expect(result).toBe("not-a-date");
  });
});

describe("getDaysFromNow", () => {
  it("returns positive days for future dates", () => {
    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + 10);
    const result = getDaysFromNow(futureDate.toISOString());
    expect(result).toBeGreaterThanOrEqual(9);
    expect(result).toBeLessThanOrEqual(11);
  });

  it("returns negative days for past dates", () => {
    const pastDate = new Date();
    pastDate.setDate(pastDate.getDate() - 5);
    const result = getDaysFromNow(pastDate.toISOString());
    expect(result).toBeLessThanOrEqual(-4);
    expect(result).toBeGreaterThanOrEqual(-6);
  });

  it("returns 0 for invalid date", () => {
    const result = getDaysFromNow("invalid");
    expect(result).toBe(0);
  });
});

describe("formatRelativeDate", () => {
  it("returns 'today' for current date", () => {
    const today = new Date().toISOString();
    const result = formatRelativeDate(today);
    expect(result).toBe("today");
  });

  it("returns 'in X days' for near future dates", () => {
    const future = new Date();
    future.setDate(future.getDate() + 3);
    const result = formatRelativeDate(future.toISOString());
    expect(result).toMatch(/in \d+ days?/);
  });

  it("returns 'X days ago' for near past dates", () => {
    const past = new Date();
    past.setDate(past.getDate() - 3);
    const result = formatRelativeDate(past.toISOString());
    expect(result).toMatch(/\d+ days? ago/);
  });
});
