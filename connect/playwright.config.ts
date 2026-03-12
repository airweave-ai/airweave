import { defineConfig, devices } from "@playwright/test";

const CONNECT_URL = process.env.CONNECT_URL || "http://localhost:8082";
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "html" : "list",
  timeout: 60_000,
  use: {
    baseURL: CONNECT_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: undefined, // Services started externally by CI or docker compose
});

export { CONNECT_URL, BACKEND_URL };
