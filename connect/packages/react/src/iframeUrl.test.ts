import { describe, expect, it } from "vitest";
import { buildIframeUrl, getExpectedOrigin } from "./iframeUrl";

describe("iframeUrl", () => {
  describe("buildIframeUrl", () => {
    const baseUrl = "https://connect.example.com";

    it("returns base URL when no theme is provided", () => {
      const result = buildIframeUrl(baseUrl);
      expect(result).toBe("https://connect.example.com/");
    });

    it("returns base URL when theme has no mode", () => {
      const result = buildIframeUrl(baseUrl, {});
      expect(result).toBe("https://connect.example.com/");
    });

    it("appends theme query param when mode is light", () => {
      const result = buildIframeUrl(baseUrl, { mode: "light" });
      expect(result).toBe("https://connect.example.com/?theme=light");
    });

    it("appends theme query param when mode is dark", () => {
      const result = buildIframeUrl(baseUrl, { mode: "dark" });
      expect(result).toBe("https://connect.example.com/?theme=dark");
    });

    it("preserves existing query parameters", () => {
      const result = buildIframeUrl(`${baseUrl}?existing=param`, {
        mode: "dark",
      });
      expect(result).toBe(
        "https://connect.example.com/?existing=param&theme=dark",
      );
    });

    it("handles URLs with paths", () => {
      const result = buildIframeUrl(`${baseUrl}/connect/v1`, { mode: "light" });
      expect(result).toBe("https://connect.example.com/connect/v1?theme=light");
    });
  });

  describe("getExpectedOrigin", () => {
    it("extracts origin from valid HTTPS URL", () => {
      const result = getExpectedOrigin("https://connect.example.com/path");
      expect(result).toBe("https://connect.example.com");
    });

    it("extracts origin from valid HTTP URL", () => {
      const result = getExpectedOrigin("http://localhost:3000/connect");
      expect(result).toBe("http://localhost:3000");
    });

    it("handles URLs with ports", () => {
      const result = getExpectedOrigin("https://connect.example.com:8080/path");
      expect(result).toBe("https://connect.example.com:8080");
    });

    it("handles URLs with query parameters", () => {
      const result = getExpectedOrigin(
        "https://connect.example.com?theme=dark",
      );
      expect(result).toBe("https://connect.example.com");
    });

    it("returns input for invalid URLs (fallback)", () => {
      const invalidUrl = "not-a-valid-url";
      const result = getExpectedOrigin(invalidUrl);
      expect(result).toBe(invalidUrl);
    });

    it("returns input for empty string", () => {
      const result = getExpectedOrigin("");
      expect(result).toBe("");
    });
  });
});
