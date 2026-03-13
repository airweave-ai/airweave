import type { Page } from "@playwright/test";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

interface SessionResponse {
  session_id: string;
  session_token: string;
  expires_at: string;
}

interface CollectionResponse {
  id: string;
  readable_id: string;
  name: string;
}

/**
 * Create an API key and return it. Uses the default superuser (dev mode).
 */
export async function createApiKey(): Promise<string> {
  const res = await fetch(`${BACKEND_URL}/api-keys`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "e2e-connect-test" }),
  });
  if (!res.ok) throw new Error(`Failed to create API key: ${res.status}`);
  const data = await res.json();
  return data.key;
}

/**
 * Create a collection via the backend API.
 */
export async function createCollection(
  apiKey: string,
  name: string = "e2e-connect-collection",
): Promise<CollectionResponse> {
  const res = await fetch(`${BACKEND_URL}/collections`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`Failed to create collection: ${res.status}`);
  return res.json();
}

/**
 * Create a Connect session token via the backend API.
 */
export async function createConnectSession(
  apiKey: string,
  readableCollectionId: string,
  options: {
    mode?: "all" | "connect" | "manage" | "reauth";
    allowedIntegrations?: string[];
    endUserId?: string;
  } = {},
): Promise<SessionResponse> {
  const res = await fetch(`${BACKEND_URL}/connect/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      readable_collection_id: readableCollectionId,
      mode: options.mode || "all",
      allowed_integrations: options.allowedIntegrations || null,
      end_user_id: options.endUserId || null,
    }),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  return res.json();
}

/**
 * Open a host page that embeds the Connect widget in an iframe.
 *
 * Uses page.setContent() so the host runs on about:blank. The iframe
 * loads the real Connect widget from connectUrl. postMessage between
 * about:blank (parent) and the Connect origin works because the widget
 * sends CONNECT_READY with targetOrigin "*" initially.
 */
export async function openConnectInIframe(
  page: Page,
  connectUrl: string,
  sessionToken: string,
): Promise<void> {
  const html = `<!DOCTYPE html>
<html>
<head><title>Connect E2E Host</title></head>
<body>
  <div id="status">initializing</div>
  <div id="messages"></div>
  <iframe
    id="connect-iframe"
    src="${connectUrl}"
    style="width: 400px; height: 600px; border: 1px solid #ccc;"
    allow="clipboard-read; clipboard-write"
  ></iframe>
  <script>
    const iframe = document.getElementById('connect-iframe');
    const statusEl = document.getElementById('status');
    const messagesEl = document.getElementById('messages');
    const token = ${JSON.stringify(sessionToken)};

    function logMessage(msg) {
      const div = document.createElement('div');
      div.className = 'msg';
      div.setAttribute('data-type', msg.type);
      div.textContent = JSON.stringify(msg);
      messagesEl.appendChild(div);
    }

    window.addEventListener('message', (event) => {
      const data = event.data;
      if (!data || !data.type) return;

      logMessage(data);

      if (data.type === 'CONNECT_READY') {
        statusEl.textContent = 'ready';
      }

      if (data.type === 'REQUEST_TOKEN') {
        statusEl.textContent = 'token_requested';
        iframe.contentWindow.postMessage({
          type: 'TOKEN_RESPONSE',
          requestId: data.requestId,
          token: token,
        }, '*');
      }

      if (data.type === 'STATUS_CHANGE') {
        statusEl.textContent = 'status_' + data.status.status;
      }

      if (data.type === 'CONNECTION_CREATED') {
        statusEl.textContent = 'connection_created';
        statusEl.setAttribute('data-connection-id', data.connectionId);
      }

      if (data.type === 'CLOSE') {
        statusEl.textContent = 'closed_' + data.reason;
      }
    });
  </script>
</body>
</html>`;

  await page.setContent(html, { waitUntil: "domcontentloaded" });

  // Wait for the iframe to start loading
  await page.waitForSelector("#connect-iframe", { timeout: 5_000 });
}

/**
 * Wait for the Connect widget to send a specific message type.
 */
export async function waitForMessage(
  page: Page,
  messageType: string,
  timeoutMs: number = 30_000,
): Promise<void> {
  await page.waitForSelector(`div.msg[data-type="${messageType}"]`, {
    timeout: timeoutMs,
  });
}

/**
 * Get the host page status element text.
 */
export async function getHostStatus(page: Page): Promise<string> {
  return page.locator("#status").innerText();
}
