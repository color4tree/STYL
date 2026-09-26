import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { randomUUID } from "node:crypto";

process.env.STYL_E2E_DATA_DIR ??= mkdtempSync(path.join(tmpdir(), "styl-e2e-"));
process.env.STYL_E2E_TOKEN ??= randomUUID();

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  globalTeardown: "./tests/e2e/cleanup.ts",
  use: {
    baseURL: "http://127.0.0.1:3102",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { browserName: "chromium", viewport: { width: 1440, height: 1000 } } },
    { name: "phone-chromium", use: { browserName: "chromium", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: [
    {
      command: "node tests/e2e/api-server.mjs",
      url: "http://127.0.0.1:8102/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm run build && npm run start -- --hostname 127.0.0.1 --port 3102",
      url: "http://127.0.0.1:3102",
      reuseExistingServer: false,
      env: { NEXT_PUBLIC_API_URL: "http://127.0.0.1:8102" },
      timeout: 120_000,
    },
  ],
});
