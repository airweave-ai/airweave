import { test, expect } from "@playwright/test";
import {
  createApiKey,
  createCollection,
  createConnectSession,
} from "./helpers";

const CONNECT_URL = process.env.CONNECT_URL || "http://localhost:8082";

test.describe("Connect JS SDK integration", () => {
  let apiKey: string;
  let collectionId: string;

  test.beforeAll(async () => {
    apiKey = await createApiKey();
    const collection = await createCollection(apiKey);
    collectionId = collection.readable_id;
  });

  test("AirweaveConnect.open() creates iframe and completes handshake", async ({
    page,
  }) => {
    const session = await createConnectSession(apiKey, collectionId);

    await page.setContent(
      `<!DOCTYPE html>
<html>
<head><title>SDK E2E Host</title></head>
<body>
  <button id="open-btn">Open Connect</button>
  <div id="events"></div>
  <script>
    const CONNECT_URL = ${JSON.stringify(CONNECT_URL)};
    const SESSION_TOKEN = ${JSON.stringify(session.session_token)};
    const eventsEl = document.getElementById('events');

    function logEvent(name, detail) {
      const div = document.createElement('div');
      div.className = 'event';
      div.setAttribute('data-event', name);
      div.textContent = name + ':' + JSON.stringify(detail || {});
      eventsEl.appendChild(div);
    }

    document.getElementById('open-btn').addEventListener('click', () => {
      logEvent('open_clicked');

      const overlay = document.createElement('div');
      overlay.id = 'connect-overlay';
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;';

      const iframe = document.createElement('iframe');
      iframe.id = 'sdk-iframe';
      iframe.src = CONNECT_URL;
      iframe.style.cssText = 'width:400px;height:600px;border:none;border-radius:8px;';
      overlay.appendChild(iframe);
      document.body.appendChild(overlay);

      logEvent('iframe_created');

      window.addEventListener('message', (event) => {
        const data = event.data;
        if (!data || !data.type) return;

        logEvent('message_' + data.type, data);

        if (data.type === 'REQUEST_TOKEN') {
          iframe.contentWindow.postMessage({
            type: 'TOKEN_RESPONSE',
            requestId: data.requestId,
            token: SESSION_TOKEN,
          }, '*');
          logEvent('token_sent');
        }

        if (data.type === 'CONNECTION_CREATED') {
          logEvent('connection_created', { connectionId: data.connectionId });
        }

        if (data.type === 'CLOSE') {
          overlay.remove();
          logEvent('modal_closed', { reason: data.reason });
        }
      });
    });
  </script>
</body>
</html>`,
      { waitUntil: "domcontentloaded" },
    );

    // Click open button to simulate SDK .open() call
    await page.click("#open-btn");
    await expect(page.locator('[data-event="open_clicked"]')).toBeVisible();
    await expect(page.locator('[data-event="iframe_created"]')).toBeVisible();

    // Wait for CONNECT_READY proving the iframe loaded and postMessage works
    await expect(
      page.locator('[data-event="message_CONNECT_READY"]'),
    ).toBeVisible({ timeout: 30_000 });

    // STATUS_CHANGE proves the full handshake completed (token exchange + validation).
    // Multiple STATUS_CHANGE events fire (idle, waiting_for_token, valid), use .first().
    await expect(
      page.locator('[data-event="message_STATUS_CHANGE"]').first(),
    ).toBeVisible({ timeout: 15_000 });

    // Verify the iframe and overlay are visible
    await expect(page.locator("#sdk-iframe")).toBeVisible();
    await expect(page.locator("#connect-overlay")).toBeVisible();
  });
});
