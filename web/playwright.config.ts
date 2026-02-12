import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E test configuration for the Next.js web application.
 *
 * See https://playwright.dev/docs/test-configuration for full reference.
 */
export default defineConfig({
  testDir: "./e2e",

  /* Maximum time one test can run */
  timeout: 30_000,

  /* Fail the build on CI if test.only is left in source code */
  forbidOnly: !!process.env.CI,

  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,

  /* Parallel workers: use 1 on CI for stability, half-CPU locally */
  workers: process.env.CI ? 1 : undefined,

  /* Reporter: HTML for local review, line for CI */
  reporter: process.env.CI ? "line" : "html",

  /* Shared settings for all projects */
  use: {
    baseURL: "http://localhost:3000",
    /* Collect trace on first retry for debugging */
    trace: "on-first-retry",
    /* Screenshot on failure */
    screenshot: "only-on-failure",
  },

  /* Browser projects */
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],

  /* Start the Next.js dev server before running tests */
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
