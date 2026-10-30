import { defineConfig } from "@playwright/test";

const frontendPort = Number(process.env.BIRD_E2E_FRONTEND_PORT ?? 5174);

export default defineConfig({
  testDir: "./browser-tests",
  testMatch: "workflow.spec.ts",
  reporter: "list",
  outputDir: "./test-results",
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    browserName: "chromium",
    channel: "msedge",
    headless: true,
    viewport: { width: 1440, height: 1000 },
  },
  webServer: {
    command: `npm.cmd run dev:mock -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
    url: `http://127.0.0.1:${frontendPort}`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
