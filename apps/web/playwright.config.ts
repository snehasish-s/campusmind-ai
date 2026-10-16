import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  globalSetup: "./tests/global-setup.ts",
  reporter: [
    ["list"],
    ["junit", { outputFile: "test-results/browser-results.xml" }],
  ],
  use: {
    baseURL: process.env.CM_BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: {
      ...(process.env.CM_BROWSER_PATH
        ? { executablePath: process.env.CM_BROWSER_PATH }
        : {}),
    },
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
