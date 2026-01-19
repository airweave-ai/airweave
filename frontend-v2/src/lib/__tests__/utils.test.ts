import { describe, expect, it } from "vitest";

import { cn } from "../utils";

describe("cn (className utility)", () => {
  it("merges class names", () => {
    const result = cn("foo", "bar");
    expect(result).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    const result = cn("base", true && "active", false && "hidden");
    expect(result).toBe("base active");
  });

  it("merges tailwind classes correctly", () => {
    const result = cn("px-2 py-1", "px-4");
    expect(result).toBe("py-1 px-4");
  });

  it("handles arrays of classes", () => {
    const result = cn(["a", "b"], "c");
    expect(result).toBe("a b c");
  });

  it("handles undefined and null values", () => {
    const result = cn("foo", undefined, null, "bar");
    expect(result).toBe("foo bar");
  });
});
