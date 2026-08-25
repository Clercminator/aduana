import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  // The real E2E suite shares one API, one queue worker and one PostgreSQL database.
  // Keep it serial so queue wait time is not mistaken for a product failure.
  workers: 1,
  timeout: 300_000,
  expect: { timeout: 60_000 },
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1536, height: 1024 } } }],
  reporter: [["list"]],
});
