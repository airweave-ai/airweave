import { test, expect } from "@playwright/test";
import {
  createApiKey,
  createCollection,
  createConnectSession,
  openConnectInIframe,
  waitForMessage,
} from "./helpers";

const CONNECT_URL = process.env.CONNECT_URL || "http://localhost:8082";

test.describe("Connect Widget (iframe)", () => {
  let apiKey: string;
  let collectionId: string;

  test.beforeAll(async () => {
    apiKey = await createApiKey();
    const collection = await createCollection(apiKey);
    collectionId = collection.readable_id;
  });

  test("widget loads in iframe and completes token handshake", async ({
    page,
  }) => {
    const session = await createConnectSession(apiKey, collectionId);

    await openConnectInIframe(page, CONNECT_URL, session.session_token);

    // CONNECT_READY proves the widget loaded and postMessage works
    await waitForMessage(page, "CONNECT_READY", 30_000);

    // STATUS_CHANGE arriving proves the full handshake completed:
    // CONNECT_READY → REQUEST_TOKEN → TOKEN_RESPONSE → session validated
    await waitForMessage(page, "STATUS_CHANGE", 15_000);
  });

  test("widget renders UI after successful session validation", async ({
    page,
  }) => {
    const session = await createConnectSession(apiKey, collectionId);

    await openConnectInIframe(page, CONNECT_URL, session.session_token);

    await waitForMessage(page, "STATUS_CHANGE", 30_000);

    // The iframe should now show the main Connect UI (not empty)
    const iframe = page.frameLocator("#connect-iframe");
    await expect(iframe.locator("body").first()).not.toHaveText("", {
      timeout: 10_000,
    });
  });

  test("widget respects manage mode", async ({ page }) => {
    const session = await createConnectSession(apiKey, collectionId, {
      mode: "manage",
    });

    await openConnectInIframe(page, CONNECT_URL, session.session_token);

    await waitForMessage(page, "STATUS_CHANGE", 30_000);

    const iframe = page.frameLocator("#connect-iframe");
    await expect(iframe.locator("body").first()).toBeVisible({
      timeout: 10_000,
    });
  });
});
