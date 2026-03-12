import { test, expect } from "@playwright/test";
import {
  createApiKey,
  createCollection,
  createConnectSession,
} from "./helpers";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

test.describe("Connect Session API", () => {
  let apiKey: string;
  let collectionId: string;

  test.beforeAll(async () => {
    apiKey = await createApiKey();
    const collection = await createCollection(apiKey);
    collectionId = collection.readable_id;
  });

  test("creates a session and validates it", async () => {
    const session = await createConnectSession(apiKey, collectionId);

    expect(session.session_id).toBeTruthy();
    expect(session.session_token).toBeTruthy();
    expect(session.expires_at).toBeTruthy();

    // Validate the session via the GET endpoint
    const res = await fetch(
      `${BACKEND_URL}/connect/sessions/${session.session_id}`,
      {
        headers: { Authorization: `Bearer ${session.session_token}` },
      },
    );
    expect(res.ok).toBe(true);
    const ctx = await res.json();
    expect(ctx.session_id).toBe(session.session_id);
    expect(ctx.collection_id).toBe(collectionId);
  });

  test("rejects expired or invalid tokens", async () => {
    const res = await fetch(`${BACKEND_URL}/connect/sources`, {
      headers: { Authorization: "Bearer invalid-token-value" },
    });
    expect(res.status).toBe(401);
  });

  test("session respects mode restrictions", async () => {
    // Create a connect-only session (no manage/view)
    const session = await createConnectSession(apiKey, collectionId, {
      mode: "connect",
    });

    // Listing connections should be forbidden in connect mode
    const res = await fetch(`${BACKEND_URL}/connect/source-connections`, {
      headers: { Authorization: `Bearer ${session.session_token}` },
    });
    expect(res.status).toBe(403);
  });

  test("session lists sources", async () => {
    const session = await createConnectSession(apiKey, collectionId);

    const res = await fetch(`${BACKEND_URL}/connect/sources`, {
      headers: { Authorization: `Bearer ${session.session_token}` },
    });
    expect(res.ok).toBe(true);
    const sources = await res.json();
    expect(Array.isArray(sources)).toBe(true);
    expect(sources.length).toBeGreaterThan(0);
  });

  test("session filters by allowed_integrations", async () => {
    const session = await createConnectSession(apiKey, collectionId, {
      allowedIntegrations: ["stub"],
    });

    const res = await fetch(`${BACKEND_URL}/connect/sources`, {
      headers: { Authorization: `Bearer ${session.session_token}` },
    });
    expect(res.ok).toBe(true);
    const sources = await res.json();
    expect(sources.every((s: { short_name: string }) => s.short_name === "stub")).toBe(true);
  });
});
