import { describe, expect, it } from "vitest";
import { generateRandomSuffix } from "./sourceConfig-utils";

describe("sourceConfig-utils", () => {
  describe("generateRandomSuffix", () => {
    it("returns a 6-character string", () => {
      const result = generateRandomSuffix();
      expect(result).toHaveLength(6);
    });

    it("returns only lowercase alphanumeric characters", () => {
      const result = generateRandomSuffix();
      expect(result).toMatch(/^[a-z0-9]{6}$/);
    });

    it("generates different values on multiple calls", () => {
      const results = new Set<string>();
      for (let i = 0; i < 100; i++) {
        results.add(generateRandomSuffix());
      }
      // With 36^6 possibilities, 100 calls should produce at least 95 unique values
      expect(results.size).toBeGreaterThan(95);
    });

    it("does not contain uppercase letters", () => {
      for (let i = 0; i < 50; i++) {
        const result = generateRandomSuffix();
        expect(result).toBe(result.toLowerCase());
      }
    });

    it("does not contain special characters", () => {
      for (let i = 0; i < 50; i++) {
        const result = generateRandomSuffix();
        expect(result).not.toMatch(/[^a-z0-9]/);
      }
    });
  });
});
