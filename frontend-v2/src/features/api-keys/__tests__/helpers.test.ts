import { describe, expect, it } from "vitest";

import {
  EXPIRATION_PRESETS,
  getDaysRemaining,
  getStatusColor,
  maskKey,
} from "../utils/helpers";

describe("maskKey", () => {
  it("masks API key showing only first 8 characters", () => {
    const key = "aw_test_abcdefghijklmnop1234567890";
    const result = maskKey(key);
    expect(result).toMatch(/^aw_test_•+$/);
    expect(result.startsWith("aw_test_")).toBe(true);
  });

  it("returns short keys unchanged", () => {
    const key = "short";
    const result = maskKey(key);
    expect(result).toBe("short");
  });

  it("handles empty string", () => {
    const result = maskKey("");
    expect(result).toBe("");
  });
});

describe("getDaysRemaining", () => {
  it("returns positive number for future expiration", () => {
    const future = new Date();
    future.setDate(future.getDate() + 30);
    const result = getDaysRemaining(future.toISOString());
    expect(result).toBeGreaterThanOrEqual(29);
    expect(result).toBeLessThanOrEqual(31);
  });

  it("returns negative number for expired keys", () => {
    const past = new Date();
    past.setDate(past.getDate() - 5);
    const result = getDaysRemaining(past.toISOString());
    expect(result).toBeLessThanOrEqual(-4);
  });
});

describe("getStatusColor", () => {
  it("returns red for expired keys", () => {
    const result = getStatusColor(-1);
    expect(result).toBe("text-red-500");
  });

  it("returns amber for keys expiring within 7 days", () => {
    expect(getStatusColor(0)).toBe("text-amber-500");
    expect(getStatusColor(7)).toBe("text-amber-500");
  });

  it("returns muted for keys with more than 7 days remaining", () => {
    expect(getStatusColor(8)).toBe("text-muted-foreground");
    expect(getStatusColor(30)).toBe("text-muted-foreground");
  });
});

describe("EXPIRATION_PRESETS", () => {
  it("contains expected presets", () => {
    expect(EXPIRATION_PRESETS).toHaveLength(5);
    expect(EXPIRATION_PRESETS.map((p) => p.days)).toEqual([
      30, 60, 90, 180, 365,
    ]);
  });

  it("has 90 days as recommended", () => {
    const recommended = EXPIRATION_PRESETS.find((p) => p.recommended);
    expect(recommended?.days).toBe(90);
  });
});
